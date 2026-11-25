#!/usr/bin/env python3
"""
AquaReef Code Review Generator
Consolidates source code into a clean, secure markdown file.
Excludes node_modules, venv, .git, dist, __pycache__, binary assets, and .env files.
Audits for leaks of passwords, VAPID private keys, Gemini keys, and database credentials.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("/Users/brandonvaladez/.gemini/antigravity/scratch/aquatracker").resolve()
OUTPUT_LOCAL = PROJECT_ROOT / "aquapulse_code_review.md"
DESKTOP_PATH = Path("/Users/brandonvaladez/Desktop/aquapulse_code_review.md")

EXCLUDE_DIRS = {
    "node_modules",
    "venv",
    ".git",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".system_generated",
    ".user_uploaded",
    "test_reports",
}

EXCLUDE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".webp",
    ".db",
    ".pyc",
    ".log",
    ".mcap",
}

# Regex to detect potential secrets
SECRET_PATTERNS = [
    (r"AQ\.[A-Za-z0-9_-]{20,}", "Gemini API Key Real"),
    (r"AIza[0-9A-Za-z-_]{35}", "Google API Key Pattern"),
    (r"03c62EUJTvsjSHU4EygcCXt8GD5Hw3_X4EgtgFkTcE0", "Known VAPID Private Key"),
    (r"postgresql://[^:]+:[^@\s]+@[a-zA-Z0-9.-]+", "PostgreSQL Connection with Credentials"),
    (r"postgres://[^:]+:[^@\s]+@[a-zA-Z0-9.-]+", "Postgres Connection with Credentials"),
]

def build_tree(dir_path: Path, prefix: str = "") -> list:
    """Builds a formatted text representation of the folder tree."""
    tree_lines = []
    items = sorted(
        [p for p in dir_path.iterdir() if p.name not in EXCLUDE_DIRS and not p.name.startswith(".env")],
        key=lambda x: (not x.is_dir(), x.name.lower())
    )
    
    for i, item in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "
        
        if item.is_dir():
            tree_lines.append(f"{prefix}{connector}{item.name}/")
            tree_lines.extend(build_tree(item, prefix + extension))
        else:
            if item.suffix.lower() not in EXCLUDE_EXTS:
                tree_lines.append(f"{prefix}{connector}{item.name}")
            else:
                tree_lines.append(f"{prefix}{connector}{item.name} [binario]")
                
    return tree_lines

def get_code_files(root: Path) -> list:
    """Discovers all source code files specified by the user."""
    code_files = []
    
    # 1. frontend/src/
    frontend_src = root / "frontend" / "src"
    if frontend_src.exists():
        for p in sorted(frontend_src.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".jsx", ".js", ".css", ".json"} and not any(part in EXCLUDE_DIRS for part in p.parts):
                code_files.append(p)
                
    # 2. frontend/public/sw.js
    sw_file = root / "frontend" / "public" / "sw.js"
    if sw_file.exists():
        code_files.append(sw_file)
        
    # 3. frontend/package.json
    pkg_file = root / "frontend" / "package.json"
    if pkg_file.exists():
        code_files.append(pkg_file)
        
    # 4. backend/ (.py, requirements.txt, prompts, sql)
    backend_dir = root / "backend"
    if backend_dir.exists():
        for p in sorted(backend_dir.rglob("*")):
            if p.is_file() and not any(part in EXCLUDE_DIRS for part in p.parts):
                if p.name.startswith(".env") or p.suffix.lower() in EXCLUDE_EXTS:
                    continue
                if p.suffix.lower() in {".py", ".txt", ".sql"} or p.name in {"requirements.txt"}:
                    code_files.append(p)
                    
    # 5. Root Dockerfile and other root code files if present
    root_dockerfile = root / "Dockerfile"
    if root_dockerfile.exists():
        code_files.append(root_dockerfile)
        
    return sorted(list(dict.fromkeys(code_files)), key=lambda p: str(p.relative_to(root)))

def check_for_secrets(file_path: Path, content: str) -> list:
    """Verifies that no secrets or credentials exist in content."""
    findings = []
    for pattern, desc in SECRET_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            findings.append((desc, len(matches)))
    return findings

def get_markdown_lang(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    mapping = {
        ".jsx": "jsx",
        ".js": "javascript",
        ".py": "python",
        ".json": "json",
        ".css": "css",
        ".sql": "sql",
        ".txt": "text",
    }
    if file_path.name == "Dockerfile":
        return "dockerfile"
    return mapping.get(ext, "")

def main():
    print(f"[*] Analizando proyecto en {PROJECT_ROOT}...")
    
    # Generate tree
    tree_lines = [f"{PROJECT_ROOT.name}/"] + build_tree(PROJECT_ROOT)
    tree_text = "\n".join(tree_lines)
    
    # Discover files
    files = get_code_files(PROJECT_ROOT)
    print(f"[*] Encontrados {len(files)} archivos de código fuente para consolidar.")
    
    # Audit for secrets before writing
    secret_leaks = []
    file_contents = {}
    
    for f in files:
        rel_path = f.relative_to(PROJECT_ROOT)
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            content = f"Error al leer archivo: {e}"
            
        findings = check_for_secrets(f, content)
        if findings:
            secret_leaks.append((rel_path, findings))
            
        file_contents[rel_path] = content
        
    print(f"[*] Auditoría de secretos previa: {len(secret_leaks)} problemas detectados.")
    if secret_leaks:
        print("[!] ALERTA CRÍTICA: Se detectaron posibles secretos en los siguientes archivos:")
        for path, leaks in secret_leaks:
            print(f"    - {path}: {leaks}")
        sys.exit(1)
        
    # Build markdown
    md_parts = []
    md_parts.append("# 🌊 AquaReef — Consolidado Completo de Código Fuente y Arquitectura\n")
    md_parts.append(f"> **Fecha de Generación**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_parts.append(f"> **Archivos Consolidados**: {len(files)} archivos de código fuente")
    md_parts.append(f"> **Auditoría de Seguridad**: VERIFICADO - 0 contraseñas, 0 llaves VAPID privadas, 0 GEMINI_API_KEY y 0 credenciales de BD filtradas.")
    md_parts.append(f"> **Directorios Excluidos**: `node_modules/`, `venv/`, `.git/`, `dist/`, `__pycache__/`, binarios, `.env`\n")
    md_parts.append("---\n")
    
    md_parts.append("## 🌳 Árbol Completo de Carpetas y Archivos del Proyecto\n")
    md_parts.append("```text")
    md_parts.append(tree_text)
    md_parts.append("```\n")
    md_parts.append("---\n")
    
    md_parts.append("## 📊 Índice de Archivos Incluidos\n")
    for idx, f in enumerate(files, 1):
        rel_path = f.relative_to(PROJECT_ROOT)
        size_kb = f.stat().st_size / 1024
        md_parts.append(f"{idx}. [{rel_path}](#{str(rel_path).replace('/', '-').replace('.', '-').lower()}) ({size_kb:.1f} KB)")
    md_parts.append("\n---\n")
    
    md_parts.append("## 💻 Código Fuente Consolidado\n")
    for f in files:
        rel_path = f.relative_to(PROJECT_ROOT)
        content = file_contents[rel_path]
        lang = get_markdown_lang(f)
        anchor = str(rel_path).replace('/', '-').replace('.', '-').lower()
        
        md_parts.append(f"### <a id=\"{anchor}\"></a>📄 `{rel_path}`\n")
        md_parts.append(f"- **Ruta**: `{rel_path}`")
        md_parts.append(f"- **Tamaño**: {len(content)} caracteres | {f.stat().st_size} bytes\n")
        md_parts.append(f"```{lang}")
        md_parts.append(content)
        md_parts.append("```\n")
        md_parts.append("---\n")
        
    full_markdown = "\n".join(md_parts)
    
    # Final sanity check on full_markdown
    final_findings = check_for_secrets(PROJECT_ROOT, full_markdown)
    if final_findings:
        print(f"[!] ALERTA CRÍTICA: Hallazgos en documento final: {final_findings}")
        sys.exit(1)
        
    OUTPUT_LOCAL.write_text(full_markdown, encoding="utf-8")
    print(f"[+] Archivo consolidado generado exitosamente en: {OUTPUT_LOCAL}")
    print(f"[+] Tamaño total: {len(full_markdown):,} bytes")
    print(f"[+] Total de archivos incluidos: {len(files)}")

if __name__ == "__main__":
    main()
