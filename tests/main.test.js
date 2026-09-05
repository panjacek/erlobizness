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
                    <select id="theme-select"></select>
                    <div id="player-stats"></div>
                    <div id="game-log"></div>
                    <div id="board-container"></div>
                    <div id="dice-container"></div>
                    <div id="dice-visual"></div>
                    <div id="dice-total"></div>
                    <button id="trade-btn"></button>
                    <div id="trade-init-modal"></div>
                    <select id="trade-target-select"></select>
                    <select id="trade-action-select"></select>
                    <select id="trade-property-select"></select>
                    <input id="trade-price-input" type="number">
                    <button id="trade-init-send"></button>
                    <button id="trade-init-cancel"></button>
                    <div id="trade-respond-modal"></div>
                    <p id="trade-respond-text"></p>
                    <div id="trade-counter-section"></div>
                    <input id="trade-counter-price" type="number">
                    <button id="trade-btn-accept"></button>
                    <button id="trade-btn-reject"></button>
                    <button id="trade-btn-counter"></button>
                    <button id="trade-btn-send-counter"></button>
                    <div id="buy-modal"></div>
                    <p id="buy-modal-text"></p>
                    <button id="buy-accept"></button>
                    <button id="buy-decline"></button>
                    <div id="auction-modal"></div>
                    <p id="auction-text"></p>
                    <span id="auction-current-bid"></span>
                    <div id="auction-bid-section"></div>
                    <input id="auction-bid-input" type="number">
                    <button id="auction-bid-btn"></button>
                    <button id="auction-pass-btn"></button>
                    <div id="game-over-modal"></div>
                    <p id="game-over-text"></p>
                    <button id="game-over-reset"></button>
                </body>
            </html>
        `,
			{ runScripts: "dangerously", resources: "usable", url: "http://localhost" },
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
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
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

	it("checkAuctionState shows modal when auction active", () => {
		window.gameState = {
			players: [
				{ name: "A", position: 0, money: 3000, properties: [], in_jail: false },
				{ name: "B", position: 0, money: 3000, properties: [], in_jail: false },
			],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			active_auction: {
				field: 3,
				starting_price: 60,
				current_bid: 0,
				current_bidder: null,
				auction_turn: 0,
				pass_count: 0,
			},
		};

		window.checkAuctionState();

		const modal = document.getElementById("auction-modal");
		expect(modal.style.display).toBe("block");
	});

	it("checkAuctionState hides modal when no auction", () => {
		window.gameState = {
			players: [{ name: "A", position: 0, money: 3000, properties: [], in_jail: false }],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			active_auction: null,
		};

		window.checkAuctionState();

		const modal = document.getElementById("auction-modal");
		expect(modal.style.display).toBe("none");
	});

	it("checkAuctionState hides modal when not my turn", () => {
		window.gameState = {
			players: [
				{ name: "A", position: 0, money: 3000, properties: [], in_jail: false },
				{ name: "B", position: 0, money: 3000, properties: [], in_jail: false },
			],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			active_auction: {
				field: 3,
				starting_price: 60,
				current_bid: 0,
				current_bidder: null,
				auction_turn: 1,
				pass_count: 0,
			},
		};

		window.checkAuctionState();

		const modal = document.getElementById("auction-modal");
		expect(modal.style.display).toBe("none");
	});

	it("checkAuctionState shows bid buttons only on my turn", () => {
		window.gameState = {
			players: [
				{ name: "A", position: 0, money: 3000, properties: [], in_jail: false },
				{ name: "B", position: 0, money: 3000, properties: [], in_jail: false },
			],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			active_auction: {
				field: 3,
				starting_price: 60,
				current_bid: 0,
				current_bidder: null,
				auction_turn: 0,
				pass_count: 0,
			},
		};

		window.checkAuctionState();

		expect(document.getElementById("auction-bid-btn").style.display).toBe("block");
		expect(document.getElementById("auction-pass-btn").style.display).toBe("block");

		// Now set to other player's turn
		window.gameState.active_auction.auction_turn = 1;
		window.checkAuctionState();

		expect(document.getElementById("auction-bid-btn").style.display).toBe("none");
		expect(document.getElementById("auction-pass-btn").style.display).toBe("none");
	});

	it("checkAuctionState sets input value and min to starting_price when no bids", () => {
		window.gameState = {
			players: [
				{ name: "A", position: 0, money: 3000, properties: [], in_jail: false },
				{ name: "B", position: 0, money: 3000, properties: [], in_jail: false },
			],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			active_auction: {
				field: 3,
				starting_price: 150,
				current_bid: 0,
				current_bidder: null,
				auction_turn: 0,
				pass_count: 0,
			},
		};

		window.checkAuctionState();

		const input = document.getElementById("auction-bid-input");
		expect(Number(input.value)).toBe(150);
		expect(Number(input.min)).toBe(150);
	});

	it("checkAuctionState sets input value and min to current_bid+1 after bids", () => {
		window.gameState = {
			players: [
				{ name: "A", position: 0, money: 3000, properties: [], in_jail: false },
				{ name: "B", position: 0, money: 3000, properties: [], in_jail: false },
			],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			active_auction: {
				field: 3,
				starting_price: 150,
				current_bid: 200,
				current_bidder: 1,
				auction_turn: 0,
				pass_count: 0,
			},
		};

		window.checkAuctionState();

		const input = document.getElementById("auction-bid-input");
		expect(Number(input.value)).toBe(201);
		expect(Number(input.min)).toBe(201);
	});

	it("checkPurchaseState shows modal when pending", () => {
		window.gameState = {
			players: [{ name: "A", position: 0, money: 3000, properties: [], in_jail: false }],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			pending_purchase: { field: 3, price: 120, player_idx: 0 },
			game_over: false,
		};

		window.checkPurchaseState();

		const modal = document.getElementById("buy-modal");
		expect(modal.style.display).toBe("block");
		const text = document.getElementById("buy-modal-text").textContent;
		expect(text).toContain("120");
	});

	it("checkGameOverState shows modal when game over", () => {
		window.gameState = {
			players: [
				{ name: "A", position: 0, money: 3000, properties: [], in_jail: false },
				{ name: "B", position: 0, money: -100, properties: [], in_jail: false },
			],
			board: Array(40).fill({ name: "Field", type: "city" }),
			current_player_idx: 0,
			game_over: true,
			winner: "A",
		};

		window.checkGameOverState();

		const modal = document.getElementById("game-over-modal");
		expect(modal.style.display).toBe("block");
		expect(document.getElementById("game-over-text").textContent).toContain("A");
	});

	it("addLog prepends entries", () => {
		window.addLog("first");
		window.addLog("second");

		const log = document.getElementById("game-log");
		const entries = log.querySelectorAll(".log-entry");
		expect(entries.length).toBe(2);
		expect(entries[0].textContent).toBe("second");
		expect(entries[1].textContent).toBe("first");
	});
});
