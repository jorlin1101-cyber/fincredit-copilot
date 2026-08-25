// This project was developed with assistance from AI tools.
const quote = (file) => `"${file.replaceAll('"', '\\"')}"`;

export default {
    "packages/ui/**/*.{js,jsx,ts,tsx,css,md,html,json}": (files) => [
        `pnpm --filter ui prettier --write -- ${files.map(quote).join(" ")}`,
        `pnpm --filter ui eslint --max-warnings 0 -- ${files.map(quote).join(" ")}`,
    ],
    "packages/api/**/*.py": (files) => [
        `uv run --directory packages/api ruff format --respect-gitignore -- ${files.map(quote).join(" ")}`,
        `uv run --directory packages/api ruff check -- ${files.map(quote).join(" ")}`,
    ],
};
