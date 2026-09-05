import { expect, test } from "@playwright/test";

// Persistence (ERLO_SAVE_PATH) survives across server restarts, so every
// suite must start from a clean, save-file-free state.
test.beforeAll(async ({ request }) => {
	await request.post("/reset");
});

async function rollUntilCurrentPlayerOwnsProperty(page) {
	// Drive turns through the API (no animation), resolving buy decisions
	// along the way; poll /state until the CURRENT player owns a property
	// (only they can propose a sale), then return that state.
	for (let i = 0; i < 80; i++) {
		const resp = await (await page.request.post("/roll")).json();
		if (resp.state.pending_purchase) {
			await page.request.post("/purchase/decide", {
				data: { decision: "buy" },
			});
		}
		// Buy may have started auction (can't afford) — pass to end it
		const stateAfterBuy = await (await page.request.get("/state")).json();
		if (stateAfterBuy.active_auction) {
			await page.request.post("/auction/pass", {
				data: { player_idx: stateAfterBuy.active_auction.auction_turn },
			});
		}
		const state = await (await page.request.get("/state")).json();
		if (state.players[state.current_player_idx].properties.length > 0) {
			return state;
		}
	}
	throw new Error("Current player owns nothing after 80 rolls");
}

test.describe("ErloBiznes UI", () => {
	test("board renders 40 fields and 2 player markers", async ({ page }) => {
		await page.goto("/");
		await expect(page.locator(".field")).toHaveCount(40);
		await expect(page.locator(".player-marker")).toHaveCount(2);
		await expect(page.locator("#roll-btn")).toBeVisible();
	});

	test("roll shows dice, total and log entry, re-enables button", async ({ page }) => {
		await page.goto("/");
		await expect(page.locator(".field")).toHaveCount(40);

		const posBefore = (await (await page.request.get("/state")).json()).players[0].position;

		await page.click("#roll-btn");

		// Double-click guard: button is disabled while rolling
		await expect(page.locator("#roll-btn")).toBeDisabled();

		const diceContainer = page.locator("#dice-container");
		await expect(diceContainer).toBeVisible();
		await expect(page.locator("#dice-total")).not.toHaveText("0");
		await expect(page.locator("#dice-visual .die").first()).toBeVisible();
		await expect(page.locator("#game-log .log-entry").first()).not.toBeEmpty();

		// Resolve an eventual buy decision through the UI - an API-only
		// decide would leave the page's stale gameState blocking the button
		await expect(async () => {
			if (await page.locator("#buy-modal").isVisible()) {
				await page.click("#buy-decline");
				await expect(page.locator("#buy-modal")).not.toBeVisible();
			}
			// Declining starts auction — pass via API (modal may be hidden)
			const state = await (await page.request.get("/state")).json();
			if (state.active_auction) {
				await page.request.post("/auction/pass", {
					data: { player_idx: state.active_auction.auction_turn },
				});
				await page.evaluate(() => fetchState());
			}
			await expect(page.locator("#roll-btn")).toBeEnabled({ timeout: 1_000 });
		}).toPass({ timeout: 10_000 });

		// The active pawn actually ended up where the server says
		const state = await (await page.request.get("/state")).json();
		const moverIdx = (state.current_player_idx + state.players.length - 1) % state.players.length;
		if (moverIdx === 0 && !state.players[0].in_jail) {
			expect(state.players[0].position).not.toBe(posBefore);
			// Both pawns may share a field - assert visibility, not count
			const marker = page.locator(`#field-${state.players[0].position} .player-marker`).first();
			await expect(marker).toBeVisible();
		}
	});

	test("i18n keys are applied to static DOM", async ({ page }) => {
		await page.goto("/");
		const h3 = page.locator('h3[data-i18n="Dziennik zdarzeń"]');
		await expect(h3).toBeVisible();
		await expect(h3).toHaveText("Dziennik zdarzeń");
	});

	test("trade flow: propose sale, counter-offer, accept", async ({ page }) => {
		const state = await rollUntilCurrentPlayerOwnsProperty(page);
		await page.goto("/");

		const propName = state.players[state.current_player_idx].properties[0].name;

		await expect(page.locator("#trade-btn")).toBeVisible();
		await page.click("#trade-btn");
		await expect(page.locator("#trade-init-modal")).toBeVisible();

		// Current player sells their own property to the other player
		await page.selectOption("#trade-action-select", "sell");
		const propOption = page.locator("#trade-property-select option", { hasText: propName }).first();
		await expect(propOption).toHaveCount(1);
		await page.selectOption("#trade-property-select", await propOption.getAttribute("value"));
		await page.fill("#trade-price-input", "50");

		await page.click("#trade-init-send");
		await expect(page.locator("#trade-respond-modal")).toBeVisible();
		await expect(page.locator("#trade-respond-text")).toContainText(`${propName} za 50`);

		// Counter with a different price: section swaps in, buttons swap out
		await page.click("#trade-btn-counter");
		await expect(page.locator("#trade-counter-section")).toBeVisible();
		await expect(page.locator("#trade-btn-accept")).not.toBeVisible();
		await page.fill("#trade-counter-price", "500");
		await page.click("#trade-btn-send-counter");

		// Modal re-renders with the countered price as the active offer
		await expect(page.locator("#trade-btn-accept")).toBeVisible();
		await expect(page.locator("#trade-respond-text")).toContainText(`${propName} za 500`);

		const stateBefore = await (await page.request.get("/state")).json();
		await page.click("#trade-btn-accept");
		await expect(page.locator("#trade-respond-modal")).not.toBeVisible();

		// Ownership actually swapped at the countered price
		const stateAfter = await (await page.request.get("/state")).json();
		expect(stateAfter.active_trade).toBeNull();
		const buyerIdx = stateAfter.current_player_idx === 0 ? 1 : 0;
		const sellerIdx = state.current_player_idx;
		const prop = stateAfter.players[buyerIdx].properties.find((p) => p.name === propName);
		expect(prop).toBeDefined();
		const moneyDelta = stateAfter.players[sellerIdx].money - stateBefore.players[sellerIdx].money;
		expect(moneyDelta).toBe(500);
		await expect(page.locator("#game-log")).toContainText("Transakcja zakończona");
	});

	test("trade reject closes loop without transaction", async ({ page }) => {
		const state = await rollUntilCurrentPlayerOwnsProperty(page);
		await page.goto("/");

		const propName = state.players[state.current_player_idx].properties[0].name;

		await page.click("#trade-btn");
		await page.selectOption("#trade-action-select", "sell");
		const propOption = page.locator("#trade-property-select option", { hasText: propName }).first();
		await page.selectOption("#trade-property-select", await propOption.getAttribute("value"));
		await page.fill("#trade-price-input", "50");
		await page.click("#trade-init-send");
		await expect(page.locator("#trade-respond-modal")).toBeVisible();

		await page.click("#trade-btn-reject");
		await expect(page.locator("#trade-respond-modal")).not.toBeVisible();

		const after = await (await page.request.get("/state")).json();
		expect(after.active_trade).toBeNull();
		// Seller still owns it, no money moved hands implicitly
		const stillOwned = after.players[state.current_player_idx].properties.find(
			(p) => p.name === propName,
		);
		expect(stillOwned).toBeDefined();
		await expect(page.locator("#game-log")).not.toContainText("Transakcja zakończona");
	});

	test("reset clears log and hides dice", async ({ page }) => {
		await page.goto("/");
		await page.click("#roll-btn");
		await expect(page.locator("#game-log .log-entry").first()).not.toBeEmpty({
			timeout: 8_000,
		});

		// The roll may have left a pending purchase whose modal blocks clicks
		if (await page.locator("#buy-modal").isVisible()) {
			await page.click("#buy-decline");
			await expect(page.locator("#buy-modal")).not.toBeVisible();
		}
		// Declining may have started an auction — pass via API
		const stateAfterRoll = await (await page.request.get("/state")).json();
		if (stateAfterRoll.active_auction) {
			await page.request.post("/auction/pass", {
				data: { player_idx: stateAfterRoll.active_auction.auction_turn },
			});
			await page.evaluate(() => fetchState());
		}

		await page.click("#reset-btn");
		await expect(page.locator("#dice-container")).not.toBeVisible();
		await expect(page.locator("#game-log .log-entry")).toHaveCount(1);
	});

	test("buy decision modal appears for unowned field", async ({ page }) => {
		let pending = null;
		for (let i = 0; i < 60; i++) {
			const resp = await (await page.request.post("/roll")).json();
			if (resp.state.pending_purchase) {
				pending = resp.state.pending_purchase;
				break;
			}
			// API may have started auction (can't afford) — pass to end turn
			if (resp.state.active_auction) {
				await page.request.post("/auction/pass", {
					data: { player_idx: resp.state.active_auction.auction_turn },
				});
			}
		}
		test.skip(!pending, "Never landed on an unowned field");

		const fieldName = (await (await page.request.get("/state")).json()).board[pending.field].name;

		await page.goto("/");
		await expect(page.locator("#buy-modal")).toBeVisible();
		await expect(page.locator("#buy-modal-text")).toContainText(fieldName);
		await expect(page.locator("#roll-btn")).toBeDisabled();

		await page.click("#buy-decline");
		await expect(page.locator("#buy-modal")).not.toBeVisible();

		// Declining starts auction — pass via API (modal hidden for non-active player)
		const afterDecline = await (await page.request.get("/state")).json();
		if (afterDecline.active_auction) {
			await page.request.post("/auction/pass", {
				data: { player_idx: afterDecline.active_auction.auction_turn },
			});
		}

		// Force frontend to re-fetch stale state after API pass
		await page.evaluate(() => fetchState());
		await expect(page.locator("#roll-btn")).toBeEnabled({ timeout: 15_000 });

		const state = await (await page.request.get("/state")).json();
		expect(state.pending_purchase).toBeNull();
		const ownedNames = state.players.flatMap((p) => p.properties.map((pr) => pr.name));
		expect(ownedNames).not.toContain(fieldName);
	});

	test("game over overlay shows winner and resets", async ({ page }) => {
		const resp = await page.request.post("/debug/state", {
			data: {
				state: {
					version: 1,
					players: [
						{
							name: "Jo",
							position: 0,
							money: -100,
							in_jail: false,
							jail_turns: 0,
							property_ids: [],
						},
						{
							name: "Zed",
							position: 0,
							money: 3000,
							in_jail: false,
							jail_turns: 0,
							property_ids: [],
						},
					],
					deck_red: [],
					deck_blue: [],
					active_trade: null,
					pending_purchase: null,
					game_over: true,
					current_player_idx: 0,
				},
			},
		});
		expect(resp.ok()).toBeTruthy();

		await page.goto("/");
		await expect(page.locator("#game-over-modal")).toBeVisible();
		await expect(page.locator("#game-over-text")).toContainText("Zed");
		await expect(page.locator("#roll-btn")).toBeDisabled();

		await page.click("#game-over-reset");
		await expect(page.locator("#game-over-modal")).not.toBeVisible();

		const state = await (await page.request.get("/state")).json();
		expect(state.game_over).toBe(false);
		for (const p of state.players) {
			expect(p.money).toBe(3000);
		}

		// Do not poison later tests with injected state
		await page.request.post("/reset");
	});
});
