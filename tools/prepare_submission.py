"""Prepare immutable GitHub method descriptors from a clean standalone Git commit.

This tool reads Git objects locally. It neither contacts GitHub nor signs or
submits a method. Keep generated descriptors outside the submitted source tree.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = {"python": "3.11", "dependencies": [], "network": "none"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *arguments], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60).stdout


def repository_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment
            or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", parsed.path)):
        raise ValueError("Use a public repository URL: https://github.com/OWNER/REPOSITORY")
    owner, repo = parsed.path[1:].split("/")
    repo = repo.removesuffix(".git")
    if owner in (".", "..") or repo in ("", ".", ".."):
        raise ValueError("Invalid GitHub repository coordinates")
    return f"https://github.com/{owner}/{repo}"


def commit_files(commit: str) -> dict[str, bytes]:
    # Reject export attributes before archiving, including attributes that hide
    # themselves. GitHub downloads must expose the same complete source tree.
    names = git("ls-tree", "-r", "--name-only", "-z", commit).decode("utf-8").split("\0")
    if any(PurePosixPath(name).name in (".gitattributes", ".gitmodules") for name in names if name):
        raise ValueError("Remove .gitattributes and submodules from this standalone submission repository")
    archive_bytes = git("archive", "--format=tar", commit)
    if len(archive_bytes) > 40 * 1024 * 1024:
        raise ValueError("Source tar exceeds the validator's expanded archive limit")
    files = {}
    total, entries = 0, 0
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive:
            entries += 1
            if entries > 4096:
                raise ValueError("Source exceeds the validator's 4096 archive entry limit")
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in member.name:
                raise ValueError("Invalid source path in Git archive")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("Symlinks, submodules and other special source entries are not supported")
            if (".git" in path.parts or any(part in ("var", "secrets", ".venv", "__pycache__") for part in path.parts)
                    or path.name.startswith(".env") or path.suffix.lower() in
                    (".pkl", ".pickle", ".bin", ".pt", ".pth", ".token", ".password", ".pem", ".key", ".pyc")):
                raise ValueError(f"Remove runtime files, credentials or model serialization from Git: {path}")
            total += member.size
            if total > 32 * 1024 * 1024:
                raise ValueError("Source exceeds the validator's 32 MiB expanded source limit")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Unreadable source archive entry")
            body = stream.read()
            if body.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError("Git LFS pointers are not usable by the validator source adapter")
            files[path.as_posix()] = body
    return files


def sources_for_policy(policy: dict, requested: list[str]) -> list[dict]:
    sources = policy["program"]["sources"]
    approved, seen = {}, set()
    for source in sources:
        if (not isinstance(source, dict) or set(source) != {"source_id", "license_id", "uri", "approved"}
                or not isinstance(source["source_id"], str) or not IDENTIFIER.fullmatch(source["source_id"])
                or not isinstance(source["license_id"], str) or not 1 <= len(source["license_id"]) <= 128
                or not isinstance(source["uri"], str) or not 1 <= len(source["uri"]) <= 2048):
            raise ValueError("Policy sources must contain complete Source records")
        if source["source_id"] in seen:
            raise ValueError("Duplicate source identifiers in policy")
        seen.add(source["source_id"])
        if source["approved"] is True:
            approved[source["source_id"]] = source
    selected = requested or list(approved)
    if not selected or len(set(selected)) != len(selected) or any(s not in approved for s in selected):
        raise ValueError("Choose unique, already approved source IDs from this public task policy")
    return [approved[s] for s in selected]


def write_json(path: Path, value) -> None:
    path.write_bytes(canonical(value) + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--policy", type=Path, required=True, help="Complete published TaskPolicy JSON")
    parser.add_argument("--commit", default="HEAD", help="Local Git ref; resolved to a full fixed commit")
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--method-license-id", default="MIT")
    parser.add_argument("--output", type=Path, default=ROOT / "var/submission")
    args = parser.parse_args()
    repository = repository_url(args.repository)
    if Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() != ROOT:
        raise ValueError("Copy miner-submission to its own directory and initialize a standalone Git repository first")
    if git("status", "--porcelain", "--untracked-files=normal").strip():
        raise ValueError("Commit all source changes first; generated files and public policies belong under ignored var/")
    commit = git("rev-parse", "--verify", "--end-of-options", args.commit + "^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("The protocol requires a 40-character Git commit")
    files = commit_files(commit)
    if not {"generator.py", "curriculum.py", "dependencies.json", "LICENSE"} <= files.keys():
        raise ValueError("Commit the complete generator, dependencies.json and method license")
    dependencies = json.loads(files["dependencies.json"])
    if dependencies != DEPENDENCIES:
        raise ValueError("This template only supports the approved Python 3.11 standard-library environment")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    task_id = policy["task_id"]
    if not isinstance(task_id, str) or not IDENTIFIER.fullmatch(task_id):
        raise ValueError("Policy task_id is not a valid protocol identifier")
    if args.method_license_id not in policy["program"]["allowed_generator_licenses"]:
        raise ValueError("The method license is not allowed by this policy")
    dependencies_sha256 = digest(dependencies)
    if dependencies_sha256 not in policy["allowed_dependencies"]:
        raise ValueError("The task has not approved this template's standard-library dependency declaration")
    sources = sources_for_policy(policy, args.source_id)
    # Path's component ordering matches shared.artifacts.tree_manifest, including
    # sibling paths such as a/b.py and a.txt. Raw string sorting would differ.
    manifest_files = [{"path": name, "size": len(files[name]), "sha256": hashlib.sha256(files[name]).hexdigest()}
                      for name in sorted(files, key=lambda name: PurePosixPath(name).parts)]
    tree_sha256 = digest(manifest_files)
    descriptor = {"repository": repository, "commit": commit, "tree_sha256": tree_sha256,
                  "dependencies_sha256": dependencies_sha256, "method_license_id": args.method_license_id,
                  "entrypoint": "generator.py", "sources": sources}
    if len(canonical(descriptor)) > 7 * 1024:
        raise ValueError("Method sources leave too little room in the signed submission; select fewer --source-id entries")
    method_hash = digest({"tree_sha256": tree_sha256, "dependencies_sha256": dependencies_sha256,
                          "entrypoint": "generator.py", "sources": sorted(sources, key=lambda s: s["source_id"])})
    output = args.output.expanduser().resolve()
    # Avoid overwriting tracked source or including the descriptor in its own hash.
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "var"):
        raise ValueError("Generated files inside the repository must be placed under var/")
    if ROOT.is_relative_to(output):
        raise ValueError("Output must not contain the submission repository")
    output.mkdir(parents=True, exist_ok=False)
    source_root = output / "source"
    source_root.mkdir()
    for name, body in files.items():
        target = source_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    write_json(output / "methods.json", {task_id: descriptor})
    write_json(output / "method.json", descriptor)
    write_json(output / "source-manifest.json", {"files": manifest_files, "sha256": tree_sha256})
    write_json(output / "snapshot.json", {"commit": commit, "tree_sha256": tree_sha256,
                                         "dependencies_sha256": dependencies_sha256})
    print(json.dumps({"task_id": task_id, "commit": commit, "method_hash": method_hash,
                      "methods_file": str(output / "methods.json"),
                      "notice": "Prepared locally. Publish this exact commit before submitting; GitHub reachability was not checked."},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
