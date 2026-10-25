"""Create a source archive without environments, outputs, secrets or VCS metadata."""

import zipfile
from pathlib import Path

EXCLUDED = {
    ".venv",
    ".git",
    "runs",
    "dist",
    "build",
    "__pycache__",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "htmlcov",
}


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / "dist" / "rowproof-agent-harness-0.1.0-source.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, mode="x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if any(part in EXCLUDED or part.endswith(".egg-info") for part in relative.parts):
                continue
            if path.name in {".env", ".coverage", ".DS_Store"} or path.is_symlink():
                continue
            if path.is_file():
                archive.write(path, Path(root.name) / relative)
    print(destination)


if __name__ == "__main__":
    main()
