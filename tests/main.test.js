import fs from "node:fs";
import path from "node:path";
import { JSDOM } from "jsdom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const scriptPath = path.resolve(__dirname, "../src/erlobiznes/static/main.js");
const scriptContent = fs.readFileSync(scriptPath, "utf8");

describe("main.js tests", () => {
	let dom;
	let window;
	let document;

	beforeEach(() => {
		// Mock HTML structure needed by main.js
		dom = new JSDOM(
			`
            <!DOCTYPE html>
            <html>
                <body>
                    <button id="roll-btn"></button>
                    <button id="reset-btn"></button>
                    <div id="player-stats"></div>
                    <div id="game-log"></div>
                    <div id="board-container"></div>
                    <div id="dice-container"></div>
                    <div id="dice-visual"></div>
                    <div id="dice-total"></div>
                </body>
            </html>
        `,
			{ runScripts: "dangerously", resources: "usable" },
		);

		window = dom.window;
		document = window.document;
		global.document = document;
		global.window = window;
		const mockFetch = vi.fn().mockImplementation(() =>
			Promise.resolve({
				json: () =>
					Promise.resolve({
						players: [],
						board: Array(40).fill({ name: "Field", type: "city" }),
					}),
			}),
		);
		global.fetch = mockFetch;
		window.fetch = mockFetch;
		global.setTimeout = window.setTimeout;
		global.HTMLElement = window.HTMLElement;
		global.Node = window.Node;

		// Execute the script
		const scriptElement = document.createElement("script");
		scriptElement.textContent = scriptContent;
		document.body.appendChild(scriptElement);
	});

	it("should have basic elements defined", () => {
		expect(document.getElementById("roll-btn")).toBeDefined();
	});

	it("renderDiceVisual should create die elements", () => {
		// We need to access functions from window if they are defined globally
		const renderDiceVisual = window.renderDiceVisual;
		expect(renderDiceVisual).toBeDefined();

		renderDiceVisual([[3, 4]]);
		const diceVisual = document.getElementById("dice-visual");
		const dice = diceVisual.querySelectorAll(".die");
		expect(dice.length).toBe(2);
		expect(dice[0].className).toContain("die-3");
		expect(dice[1].className).toContain("die-4");
	});

	it("renderDiceVisual should handle multiple pairs", () => {
		window.renderDiceVisual([
			[3, 4],
			[2, 2],
		]);
		const diceVisual = document.getElementById("dice-visual");
		const dice = diceVisual.querySelectorAll(".die");
		expect(dice.length).toBe(4);
		expect(dice[3].className).toContain("die-2");
	});

	it("validateBoard should log error if fields are not 40", () => {
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => { });
		window.validateBoard();
		expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining("Expected 40 fields"));
		consoleSpy.mockRestore();
	});
	it("updateMarkers should apply ownership classes", () => {
		// Mock gameState with a player owning a property
		window.gameState = {
			players: [
				{
					name: "Player 1",
					position: 0,
					properties: [{ name: "Field 1" }],
					in_jail: false,
				},
			],
			board: [
				{ name: "Field 0", type: "start" },
				{ name: "Field 1", type: "city", country: "grecja" },
			],
			current_player_idx: 0,
		};

		// Render board first
		window.renderBoard();

		// Update markers
		window.updateMarkers();

		const field1 = document.getElementById("field-1");
		expect(field1.className).toContain("owned-p0");
	});
});
