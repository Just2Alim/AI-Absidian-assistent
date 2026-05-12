use std::env;
use std::path::{Component, Path, PathBuf};

fn canonical_root(raw: &str) -> Result<PathBuf, String> {
    Path::new(raw)
        .canonicalize()
        .map_err(|err| format!("cannot resolve root: {err}"))
}

fn resolve_candidate(raw: &str) -> Result<PathBuf, String> {
    let path = Path::new(raw);
    if path.exists() {
        return path
            .canonicalize()
            .map_err(|err| format!("cannot resolve path: {err}"));
    }

    let parent = path
        .parent()
        .ok_or_else(|| "path has no parent".to_string())?;
    let file_name = path
        .file_name()
        .ok_or_else(|| "path has no filename".to_string())?;
    let resolved_parent = parent
        .canonicalize()
        .map_err(|err| format!("cannot resolve parent: {err}"))?;
    Ok(resolved_parent.join(file_name))
}

fn contains_git(path: &Path) -> bool {
    path.components().any(|component| {
        matches!(component, Component::Normal(value) if value == ".git")
    })
}

fn validate_path(root: &str, candidate: &str) -> Result<PathBuf, String> {
    let root = canonical_root(root)?;
    let candidate = resolve_candidate(candidate)?;

    if contains_git(&candidate) {
        return Err("direct .git access is blocked".to_string());
    }

    candidate
        .strip_prefix(&root)
        .map_err(|_| format!("path escapes allowed root: {}", root.display()))?;

    Ok(candidate)
}

fn usage() {
    eprintln!("usage:");
    eprintln!("  obsidian-ai-native-core validate-path <allowed-root> <candidate-path>");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 4 || args[1] != "validate-path" {
        usage();
        std::process::exit(2);
    }

    match validate_path(&args[2], &args[3]) {
        Ok(path) => {
            println!("ALLOW {}", path.display());
        }
        Err(reason) => {
            println!("BLOCK {reason}");
            std::process::exit(1);
        }
    }
}
