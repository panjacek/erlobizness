const rollBtn = document.getElementById("roll-btn");
const resetBtn = document.getElementById("reset-btn");
const playerStats = document.getElementById("player-stats");
const gameLog = document.getElementById("game-log");
const boardContainer = document.getElementById("board-container");

var gameState = null;
var i18n = {};

const diceContainer = document.getElementById("dice-container");
const diceVisual = document.getElementById("dice-visual");
const diceTotal = document.getElementById("dice-total");

// Trade elements
const tradeBtn = document.getElementById("trade-btn");
const tradeInitModal = document.getElementById("trade-init-modal");
const tradeTargetSelect = document.getElementById("trade-target-select");
const tradeActionSelect = document.getElementById("trade-action-select");
const tradePropertySelect = document.getElementById("trade-property-select");
const tradePriceInput = document.getElementById("trade-price-input");
const tradeInitSendBtn = document.getElementById("trade-init-send");
const tradeInitCancelBtn = document.getElementById("trade-init-cancel");

const tradeRespondModal = document.getElementById("trade-respond-modal");
const tradeRespondText = document.getElementById("trade-respond-text");
const tradeCounterSection = document.getElementById("trade-counter-section");
const tradeCounterPrice = document.getElementById("trade-counter-price");
const tradeBtnAccept = document.getElementById("trade-btn-accept");
const tradeBtnReject = document.getElementById("trade-btn-reject");
const tradeBtnCounter = document.getElementById("trade-btn-counter");
const tradeBtnSendCounter = document.getElementById("trade-btn-send-counter");

// Purchase decision elements
const buyModal = document.getElementById("buy-modal");
const buyModalText = document.getElementById("buy-modal-text");
const buyAcceptBtn = document.getElementById("buy-accept");
const buyDeclineBtn = document.getElementById("buy-decline");
const buyMortgageSection = document.getElementById("buy-mortgage-section");
const buyMortgageList = document.getElementById("buy-mortgage-list");
const buyAuctionBtn = document.getElementById("buy-auction-btn");
const buyTryBtn = document.getElementById("buy-try-btn");

// Payment (rent/tax) elements
const paymentModal = document.getElementById("payment-modal");
const paymentModalText = document.getElementById("payment-modal-text");
const paymentMortgageList = document.getElementById("payment-mortgage-list");
const paymentResolveBtn = document.getElementById("payment-resolve-btn");

// Game over elements
const gameOverModal = document.getElementById("game-over-modal");
const gameOverText = document.getElementById("game-over-text");
const gameOverResetBtn = document.getElementById("game-over-reset");

// Auction elements
const auctionModal = document.getElementById("auction-modal");
const auctionText = document.getElementById("auction-text");
const auctionCurrentBid = document.getElementById("auction-current-bid");
const auctionBidSection = document.getElementById("auction-bid-section");
const auctionBidInput = document.getElementById("auction-bid-input");
const auctionBidBtn = document.getElementById("auction-bid-btn");
const auctionPassBtn = document.getElementById("auction-pass-btn");

function renderDiceVisual(rolls) {
	diceVisual.innerHTML = "";

	for (const pair of rolls) {
		for (const val of pair) {
			const die = document.createElement("div");
			die.className = `die die-${val}`;
			// Potential dots positions (1-7)
			for (let i = 1; i <= 7; i++) {
				const dot = document.createElement("div");
				dot.className = `dot dot-${i}`;
				die.appendChild(dot);
			}
			diceVisual.appendChild(die);
		}
	}
}

async function fetchState() {
	const res = await fetch("/state");
	gameState = await res.json();
	render();
}

async function rollDice() {
	if (rollBtn.disabled) return;
	rollBtn.disabled = true;
	try {
		const res = await fetch("/roll", { method: "POST" });
		const data = await res.json();

		const moverIdx = data.rolled_by;
		for (const move of data.moves || []) {
			diceVisual.classList.remove("rolling");
			void diceVisual.offsetWidth; // force reflow to restart animation
			diceVisual.classList.add("rolling");
			renderDiceVisual(move.roll.rolls);
			diceTotal.classList.remove("pop");
			void diceTotal.offsetWidth;
			diceTotal.classList.add("pop");
			diceTotal.textContent = move.roll.total;
			diceContainer.style.display = "block";
			// Let dice tumble/shake finish before the pawn moves
			await new Promise((r) => setTimeout(r, 900));
			await animateMovement(moverIdx, move.start, move.end);
		}

		if (data.messages) {
			for (const msg of data.messages) {
				if (msg.includes("czynsz")) {
					addLog(`💰 ${msg}`); // Fancy icons for payments
				} else {
					addLog(msg);
				}
			}
		}

		// state.current_player_idx from server is authoritative
		gameState = data.state;

		if (gameState.game_over) {
			addLog(i18n.game_over || "Game over.");
		}

		render();
	} catch (e) {
		addLog(i18n.network_error || "Connection error.");
	} finally {
		// Keep the button dead when the game ended, a trade blocks turns,
		// a buy decision is pending, a payment is pending, or an auction is in progress
		rollBtn.disabled =
			!!gameState?.game_over ||
			!!gameState?.active_trade ||
			!!gameState?.pending_purchase ||
			!!gameState?.pending_payment ||
			!!gameState?.active_auction;
	}
}

async function animateMovement(pIdx, start, end) {
	const boardSize = gameState.board.length;
	let current = start;
	const STEP_MS = 140;

	// Simple path finding (always forward)
	while (current !== end) {
		current = (current + 1) % boardSize;

		// Temporarily update position for the marker
		gameState.players[pIdx].position = current;
		updateMarkers();

		const fieldEl = document.getElementById(`field-${current}`);
		if (fieldEl) {
			fieldEl.classList.add("landed");
			setTimeout(() => fieldEl.classList.remove("landed"), 300);
		}
		await new Promise((r) => setTimeout(r, STEP_MS));
	}
}

async function resetGame() {
	const res = await fetch("/reset", { method: "POST" });
	const data = await res.json();
	gameState = data.state;
	diceContainer.style.display = "none";
	gameLog.innerHTML = "";
	addLog(i18n.game_reset || "Game Reset.");
	render();
}

function addLog(msg) {
	const div = document.createElement("div");
	div.className = "log-entry";
	div.textContent = msg;
	gameLog.prepend(div);
}

function render() {
	if (!gameState) return;

	// Render stats
	playerStats.innerHTML = gameState.players
		.map((p, idx) => {
			const isActive = idx === gameState.current_player_idx;
			const propertiesHtml =
				p.properties.length > 0
					? p.properties
							.map((prop) => {
								const colorClass = prop.country
									? `prop-${prop.country.toLowerCase().replace("ą", "a")}`
									: `prop-${prop.type}`;
								const mortgagedClass = prop.mortgaged ? "mortgaged" : "";
								const mortgagedIcon = prop.mortgaged ? " 🔒" : "";
								return `<span class="property-chip ${colorClass} ${mortgagedClass}" data-prop-id="${prop.id}">${prop.name}${mortgagedIcon}</span>`;
							})
							.join("")
					: `<span style="color: var(--text-muted)">${i18n.brak || "none"}</span>`;

			return `
        <div class="player-card ${isActive ? "active" : ""}">
            <div class="player-name">
                <span class="player-color-indicator player-${idx}-bg"></span>
                ${p.name} ${p.in_jail ? i18n.in_jail || "(In jail)" : ""}
                ${isActive ? '<span class="active-dice-icon">🎲</span>' : ""}
            </div>
            <div class="player-money">${p.money} $</div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem">
                ${i18n.titles?.["Akty Własności:"] || "Properties:"}<br>
                <div style="margin-top: 4px;">${propertiesHtml}</div>
            </div>
        </div>
`;
		})
		.join("");

	// Render board once if needed or update markers
	if (document.querySelectorAll(".field").length === 0) {
		renderBoard();
		validateBoard();
	}
	updateMarkers();
	checkTradeState();
	checkPurchaseState();
	checkPaymentState();
	checkAuctionState();
	checkGameOverState();
}

function checkTradeState() {
	if (!gameState) return;

	if (gameState.active_trade) {
		tradeBtn.style.display = "none";
		rollBtn.disabled = true; // Disable rolling while trade active

		const trade = gameState.active_trade;
		const proposerName = gameState.players[trade.proposer_idx].name;
		const targetName = gameState.players[trade.target_idx].name;

		let tradeText = "";
		if (trade.action === "buy") {
			tradeText = i18n.trade?.wants_to_buy
				? i18n.trade.wants_to_buy
						.replace("{proposer}", proposerName)
						.replace("{property}", trade.property_name)
						.replace("{price}", trade.price)
						.replace("{target}", targetName)
				: `${proposerName} wants to buy ${trade.property_name} for ${trade.price}$. Deal, ${targetName}?`;
		} else {
			tradeText = i18n.trade?.wants_to_sell
				? i18n.trade.wants_to_sell
						.replace("{proposer}", proposerName)
						.replace("{property}", trade.property_name)
						.replace("{price}", trade.price)
						.replace("{target}", targetName)
				: `${proposerName} wants to sell ${trade.property_name} for ${trade.price}$. Deal, ${targetName}?`;
		}

		tradeRespondText.textContent = tradeText;

		tradeCounterSection.style.display = "none";
		tradeBtnAccept.style.display = "block";
		tradeBtnReject.style.display = "block";
		tradeBtnCounter.style.display = "block";
		tradeBtnSendCounter.style.display = "none";
		tradeCounterPrice.value = trade.price;

		tradeRespondModal.style.display = "block";
	} else {
		tradeRespondModal.style.display = "none";
		tradeInitModal.style.display = "none";
		tradeBtn.style.display = "block";
		if (!gameState.game_over) {
			rollBtn.disabled = false;
		}
	}
}

function renderMortgageList(container, playerIdx, onMortgaged) {
	const player = gameState.players[playerIdx];
	container.innerHTML = "";
	for (const prop of player.properties) {
		if (prop.mortgaged) continue;
		const mortgageVal = prop.mortgage_value || 0;
		const row = document.createElement("div");
		row.style.cssText = "display:flex;align-items:center;gap:6px;margin:3px 0;font-size:0.8rem;";
		row.innerHTML = `<span style="flex:1;">${prop.name}</span><span style="color:var(--text-muted);">${mortgageVal}$</span>`;
		const btn = document.createElement("button");
		btn.className = "btn secondary";
		btn.style.cssText = "padding:2px 8px;font-size:0.75rem;";
		btn.textContent = "Zastaw";
		btn.addEventListener("click", async () => {
			btn.disabled = true;
			await onMortgaged(prop.id);
		});
		row.appendChild(btn);
		container.appendChild(row);
	}
	if (container.children.length === 0) {
		container.innerHTML =
			'<p style="font-size:0.8rem;color:var(--text-muted);">Brak nieruchomości do zastawienia.</p>';
	}
}

function checkPurchaseState() {
	if (!gameState) return;

	if (gameState.pending_purchase && !gameState.game_over) {
		const pp = gameState.pending_purchase;
		const field = gameState.board[pp.field];
		buyModalText.textContent = `${field.name} — ${pp.price}$`;
		if (pp.awaiting_mortgage) {
			buyAcceptBtn.style.display = "none";
			buyDeclineBtn.style.display = "none";
			buyAuctionBtn.style.display = "inline-block";
			buyMortgageSection.style.display = "block";
			const player = gameState.players[gameState.current_player_idx];
			buyTryBtn.style.display = player.money >= pp.price ? "inline-block" : "none";
			renderMortgageList(buyMortgageList, gameState.current_player_idx, async (propId) => {
				await fetch("/mortgage", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ player_idx: gameState.current_player_idx, property_id: propId }),
				})
					.then((r) => r.json())
					.then((d) => {
						if (d.state) gameState = d.state;
						if (d.messages) for (const m of d.messages) addLog(m);
					});
				await fetchState();
			});
		} else {
			buyAcceptBtn.style.display = "inline-block";
			buyDeclineBtn.style.display = "inline-block";
			buyAuctionBtn.style.display = "none";
			buyMortgageSection.style.display = "none";
			buyTryBtn.style.display = "none";
		}
		buyModal.style.display = "block";
		rollBtn.disabled = true;
	} else {
		buyModal.style.display = "none";
	}
}

function checkPaymentState() {
	if (!gameState || !gameState.pending_payment || gameState.game_over) {
		paymentModal.style.display = "none";
		return;
	}
	const pp = gameState.pending_payment;
	const player = gameState.players[pp.player_idx];
	if (pp.reason === "rent") {
		paymentModalText.textContent = `${player.name} — czynsz ${pp.amount}$`;
	} else {
		paymentModalText.textContent = `${player.name} — podatek ${pp.amount}$`;
	}
	renderMortgageList(paymentMortgageList, pp.player_idx, async (propId) => {
		await fetch("/mortgage", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ player_idx: pp.player_idx, property_id: propId }),
		})
			.then((r) => r.json())
			.then((d) => {
				if (d.state) gameState = d.state;
				if (d.messages) for (const m of d.messages) addLog(m);
			});
		await fetchState();
	});
	paymentModal.style.display = "block";
	rollBtn.disabled = true;
}

function checkAuctionState() {
	if (!gameState) return;

	if (gameState.active_auction && !gameState.game_over) {
		const auction = gameState.active_auction;
		const field = gameState.board[auction.field];
		const isMyTurn = auction.auction_turn === gameState.current_player_idx;

		auctionText.textContent = `${field.name}`;
		auctionCurrentBid.textContent = auction.current_bid;
		const minBid =
			auction.current_bidder === null ? auction.starting_price : auction.current_bid + 1;
		auctionBidInput.value = minBid;
		auctionBidInput.min = minBid;

		auctionBidSection.style.display = isMyTurn ? "block" : "none";
		auctionBidBtn.style.display = isMyTurn ? "block" : "none";
		auctionPassBtn.style.display = isMyTurn ? "block" : "none";

		auctionModal.style.display = isMyTurn ? "block" : "none";
		rollBtn.disabled = true;
	} else {
		auctionModal.style.display = "none";
	}
}

function checkGameOverState() {
	if (!gameState) return;

	if (gameState.game_over) {
		const tpl = i18n.game_over_winner || "Zwycięzca: {name}";
		gameOverText.textContent = tpl.replace("{name}", gameState.winner || "?");
		gameOverModal.style.display = "block";
		// Covers fresh page load on a finished game - rollDice's finally
		// only handles the in-session path
		rollBtn.disabled = true;
	} else {
		gameOverModal.style.display = "none";
	}
}

function validateBoard() {
	const fields = document.querySelectorAll(".field");
	if (fields.length !== 40) {
		console.error(`Board Validation Failed: Expected 40 fields, found ${fields.length}`);
	} else {
		console.log("Board Validation Passed: 40 fields correctly rendered.");
	}
}

function renderBoard() {
	if (!gameState) return;
	const decoration = boardContainer.querySelector(".board-center-decoration");
	boardContainer.innerHTML = "";
	if (decoration) boardContainer.appendChild(decoration);
	const fields = gameState.board;

	const grid = Array(121).fill(null);

	// Bottom row (Right to Left)
	for (let i = 0; i <= 10; i++) grid[120 - i] = i;
	// Left column (Bottom to Top)
	for (let i = 1; i <= 9; i++) grid[110 - i * 11] = 10 + i;
	// Top row (Left to Right)
	for (let i = 0; i <= 10; i++) grid[i] = 20 + i;
	// Right column (Top to Bottom)
	for (let i = 1; i <= 9; i++) grid[10 + i * 11] = 30 + i;

	for (let i = 0; i < 121; i++) {
		const div = document.createElement("div");
		const fieldIdx = grid[i];

		// Explicit positioning to prevent "AI slop" / auto-layout issues
		const row = Math.floor(i / 11) + 1;
		const col = (i % 11) + 1;
		div.style.gridRow = row;
		div.style.gridColumn = col;

		if (fieldIdx !== null && fieldIdx < fields.length) {
			const f = fields[fieldIdx];
			let countryClass = "";
			if (f.type === "city") {
				countryClass = f.country ? f.country.toLowerCase().replace("ą", "a") : "";
			}

			div.className = `field ${f.type} ${countryClass}`;
			div.innerHTML = `<span>${f.name}</span>`;
			div.id = `field-${fieldIdx}`;
		} else {
			div.className = "field-empty";
			div.style.visibility = "hidden";
		}
		boardContainer.appendChild(div);
	}
}

function updateMarkers() {
	// Remove existing markers and ownership classes
	for (const m of document.querySelectorAll(".player-marker")) {
		m.remove();
	}
	for (const f of document.querySelectorAll(".field")) {
		f.classList.remove("owned-p0", "owned-p1");
	}

	for (const [idx, p] of gameState.players.entries()) {
		const fieldEl = document.getElementById(`field-${p.position}`);
		if (fieldEl) {
			const marker = document.createElement("div");
			const isActive = idx === gameState.current_player_idx;
			marker.className = `player-marker player-${idx} ${isActive ? "active-p" : ""}`;
			fieldEl.appendChild(marker);
		}

		// Apply ownership borders
		for (const prop of p.properties) {
			const fieldIdx = gameState.board.findIndex((f) => f.name === prop.name);
			if (fieldIdx !== -1) {
				const ownedEl = document.getElementById(`field-${fieldIdx}`);
				if (ownedEl) {
					ownedEl.classList.add(`owned-p${idx}`);
				}
			}
		}
	}
}

rollBtn.addEventListener("click", rollDice);
resetBtn.addEventListener("click", resetGame);
gameOverResetBtn.addEventListener("click", resetGame);

tradeBtn.addEventListener("click", () => {
	tradeTargetSelect.innerHTML = "";
	for (const [idx, p] of gameState.players.entries()) {
		if (idx !== gameState.current_player_idx) {
			tradeTargetSelect.innerHTML += `<option value="${idx}">${p.name}</option>`;
		}
	}

	updateTradeProperties();
	tradeInitModal.style.display = "block";
});

tradeInitCancelBtn.addEventListener("click", () => {
	tradeInitModal.style.display = "none";
});

function updateTradeProperties() {
	const action = tradeActionSelect.value;
	const targetIdx = Number.parseInt(tradeTargetSelect.value);
	if (Number.isNaN(targetIdx)) return;
	const myIdx = gameState.current_player_idx;
	const ownerIdx = action === "buy" ? targetIdx : myIdx;
	const owner = gameState.players[ownerIdx];

	tradePropertySelect.innerHTML = "";
	for (const prop of owner.properties) {
		if (prop.mortgaged) continue;
		const propName = prop.name || prop.__name__;
		tradePropertySelect.innerHTML += `<option value="${propName}">${propName}</option>`;
	}
}

tradeTargetSelect.addEventListener("change", updateTradeProperties);
tradeActionSelect.addEventListener("change", updateTradeProperties);

tradeInitSendBtn.addEventListener("click", async () => {
	const targetIdx = Number.parseInt(tradeTargetSelect.value);
	const action = tradeActionSelect.value;
	const propName = tradePropertySelect.value;
	const price = Number.parseInt(tradePriceInput.value);

	if (!propName || Number.isNaN(price) || price <= 0) {
		alert(i18n.trade?.invalid_data || "Invalid trade data!");
		return;
	}

	tradeInitModal.style.display = "none";

	const res = await fetch("/trade/offer", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			proposer_idx: gameState.current_player_idx,
			target_idx: targetIdx,
			property_name: propName,
			price: price,
			action: action,
		}),
	});
	const data = await res.json();
	if (!res.ok) {
		addLog(data.detail || "Trade error");
		return;
	}
	handleBackendResponse(data);
});

async function sendTradeResponse(action, newPrice = null) {
	if (!gameState || !gameState.active_trade) return;
	tradeRespondModal.style.display = "none";
	const res = await fetch("/trade/respond", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			responder_idx: gameState.active_trade.target_idx,
			response: action,
			new_price: newPrice,
		}),
	});
	const data = await res.json();
	handleBackendResponse(data);
	// Explicitly re-check after handling
	checkTradeState();
}

tradeBtnAccept.addEventListener("click", () => sendTradeResponse("accept"));
tradeBtnReject.addEventListener("click", () => sendTradeResponse("reject"));

tradeBtnCounter.addEventListener("click", () => {
	tradeCounterSection.style.display = "block";
	tradeBtnAccept.style.display = "none";
	tradeBtnReject.style.display = "none";
	tradeBtnCounter.style.display = "none";
	tradeBtnSendCounter.style.display = "block";
});

tradeBtnSendCounter.addEventListener("click", () => {
	const newPrice = Number.parseInt(tradeCounterPrice.value);
	if (Number.isNaN(newPrice) || newPrice <= 0) return;
	sendTradeResponse("counter", newPrice);
});

async function sendPurchaseDecision(decision) {
	buyModal.style.display = "none";
	const res = await fetch("/purchase/decide", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ decision }),
	});
	const data = await res.json();
	handleBackendResponse(data);
}

buyAcceptBtn.addEventListener("click", () => sendPurchaseDecision("buy"));
buyDeclineBtn.addEventListener("click", () => sendPurchaseDecision("decline"));
buyAuctionBtn.addEventListener("click", async () => {
	const res = await fetch("/purchase/auction", { method: "POST" });
	const data = await res.json();
	handleBackendResponse(data);
});
buyTryBtn.addEventListener("click", async () => {
	const res = await fetch("/purchase/try", { method: "POST" });
	const data = await res.json();
	handleBackendResponse(data);
});
paymentResolveBtn.addEventListener("click", async () => {
	const res = await fetch("/payment/resolve", { method: "POST" });
	const data = await res.json();
	handleBackendResponse(data);
});

async function sendAuctionBid() {
	if (!gameState || !gameState.active_auction) return;
	const amount = Number.parseInt(auctionBidInput.value);
	if (Number.isNaN(amount) || amount <= gameState.active_auction.current_bid) return;

	const res = await fetch("/auction/bid", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			player_idx: gameState.active_auction.auction_turn,
			amount: amount,
		}),
	});
	const data = await res.json();
	if (!res.ok) {
		addLog(data.detail || "Błąd licytacji");
		return;
	}
	handleBackendResponse(data);
}

async function sendAuctionPass() {
	if (!gameState || !gameState.active_auction) return;

	const res = await fetch("/auction/pass", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			player_idx: gameState.active_auction.auction_turn,
		}),
	});
	const data = await res.json();
	if (!res.ok) {
		addLog(data.detail || "Błąd licytacji");
		return;
	}
	handleBackendResponse(data);
}

auctionBidBtn.addEventListener("click", sendAuctionBid);
auctionPassBtn.addEventListener("click", sendAuctionPass);

function handleBackendResponse(data) {
	if (data.messages) {
		for (const msg of data.messages) {
			addLog(msg);
		}
	}

	// state.current_player_idx from server is authoritative
	if (data.state) {
		gameState = data.state;
	}

	render();
}

async function loadLanguage() {
	try {
		const res = await fetch("/static/lang/pl.json");
		i18n = await res.json();
		translateDOM();
	} catch (e) {
		console.warn("Failed to load language file", e);
	}
}

function translateDOM() {
	if (!i18n.titles) return;

	for (const el of document.querySelectorAll("[data-i18n]")) {
		el.textContent = i18n.titles[el.dataset.i18n] || el.textContent;
	}
}

// Theme switching
const themeSelect = document.getElementById("theme-select");
const THEME_KEY = "erlobiznes-theme";
const THEMES = ["paper", "dark", "light", "retro"];

function applyTheme(theme) {
	const active = THEMES.includes(theme) ? theme : "paper";
	document.documentElement.dataset.theme = active;
	if (themeSelect) themeSelect.value = active;
}

applyTheme(localStorage.getItem(THEME_KEY));

if (themeSelect) {
	themeSelect.addEventListener("change", () => {
		applyTheme(themeSelect.value);
		localStorage.setItem(THEME_KEY, themeSelect.value);
	});
}

// Initial load
loadLanguage().then(() => fetchState());

// Mortgage buttons
document.addEventListener("click", async (e) => {
	if (!gameState) return;
	const chip = e.target.closest(".property-chip");
	if (!chip) return;
	const propId = Number.parseInt(chip.dataset.propId);
	if (Number.isNaN(propId)) return;

	const player = gameState.players[gameState.current_player_idx];
	const prop = player.properties.find((p) => p.id === propId);
	if (!prop) return;

	if (prop.mortgaged) {
		if (!confirm(`Wykupić zastaw ${prop.name}?`)) return;
		const res = await fetch("/unmortgage", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ player_idx: gameState.current_player_idx, property_id: propId }),
		});
		const data = await res.json();
		if (data.state) gameState = data.state;
		if (data.messages) for (const m of data.messages) addLog(m);
		render();
	} else {
		if (!confirm(`Zastawić ${prop.name}?`)) return;
		const res = await fetch("/mortgage", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ player_idx: gameState.current_player_idx, property_id: propId }),
		});
		const data = await res.json();
		if (data.state) gameState = data.state;
		if (data.messages) for (const m of data.messages) addLog(m);
		render();
	}
});
