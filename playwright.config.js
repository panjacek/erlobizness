import { defineConfig } from "@playwright/test";

// Inside the Playwright Docker container there is no uv/python: the backend
// must already be running on the host (`make up`) and is reached via
// --network host. Native runs (CI) boot the server themselves.
const inDocker = process.env.E2E_IN_DOCKER === "1";

export default defineConfig({
	testDir: "./e2e",
	timeout: 15_000,
	expect: { timeout: 5_000 },
	reporter: [["list"], ["junit", { outputFile: "test-results/junit.xml" }]],
	use: {
		baseURL: "http://localhost:8000",
		headless: true,
		launchOptions: {
			// Chromium sandbox needs privileges CI containers may not have
			args: ["--no-sandbox"],
		},
	},
	webServer: inDocker
		? undefined
		: {
				command: "uv run uvicorn erlobiznes.web_app:app --port 8000",
				port: 8000,
				reuseExistingServer: true,
				env: { PYTHONPATH: "src", ERLO_ALLOW_INJECTION: "1" },
				timeout: 30_000,
			},
});
