import os

# ---------------- CONFIGURATION ----------------
output_filename = "full_project_context.txt"

# 1. File types to include
# Added .yml and .yaml explicitly for CI files
valid_extensions = ['.py', '.toml', '.yml', '.yaml', '.json', '.md', '.sh']

# 2. Specific files to always include (no extension)
valid_filenames = ['Dockerfile', 'Makefile', '.env.example', 'ci.yml']

# 3. Folders to IGNORE (Skip these)
# We exclude '.git' (history) but we do NOT exclude '.github' (workflows)
ignore_folders = {
    'venv', '__pycache__', 'node_modules', '.idea', '.vscode',
    '.git', '.pytest_cache', 'dist', 'build'
}
# -----------------------------------------------

def pack_project():
    print(f"📦 Packing project context...")

    with open(output_filename, "w", encoding="utf-8") as outfile:
        # Header
        outfile.write(f"PROJECT CONTEXT: {os.path.basename(os.getcwd())}\n")
        outfile.write("INCLUDES: Python, Docker, Configs, and CI/CD Workflows.\n")
        outfile.write("="*50 + "\n\n")

        file_count = 0

        for root, dirs, files in os.walk("."):
            # 1. Filter directories in-place
            # This ensures we don't walk into venv or .git,
            # but we DO walk into .github since it's not in the ignore list.
            dirs[:] = [d for d in dirs if d not in ignore_folders]

            for file in files:
                is_valid_ext = any(file.endswith(ext) for ext in valid_extensions)
                is_valid_name = file in valid_filenames

                if is_valid_ext or is_valid_name:
                    file_path = os.path.join(root, file)

                    # Write File Header
                    outfile.write(f"FILE PATH: {file_path}\n")
                    outfile.write("-" * 20 + "\n")

                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            outfile.write(infile.read())
                            outfile.write("\n\n") # Buffer between files
                            file_count += 1
                    except Exception as e:
                        outfile.write(f"[Error reading file: {e}]\n\n")

    print(f"✅ Success! Packed {file_count} files (including workflows).")
    print(f"📄 Upload '{output_filename}' to Gemini.")

if __name__ == "__main__":
    pack_project()
