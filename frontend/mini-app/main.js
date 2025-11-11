const tg = window.Telegram?.WebApp;
const backendUrl = import.meta?.env?.VITE_API_URL ?? window.API_BASE_URL ?? "http://localhost:8000";

const stickersContainer = document.querySelector("#stickers");
const emptySection = document.querySelector("#empty");
const template = document.querySelector("#sticker-card");

const modal = document.querySelector("#payment-modal");
const modalClose = modal.querySelector(".close");
const modalTitle = document.querySelector("#payment-title");
const modalSubtitle = document.querySelector("#payment-subtitle");
const paymentOptions = document.querySelector("#payment-options");
const tonInvoiceSection = document.querySelector("#ton-invoice");
const tonWallet = document.querySelector("#ton-wallet");
const tonAmount = document.querySelector("#ton-amount");
const tonComment = document.querySelector("#ton-comment");
const tonExpiry = document.querySelector("#ton-expiry");
const tonStatus = document.querySelector("#ton-status");
const tonHashInput = document.querySelector("#ton-tx-hash");
const tonSubmitButton = document.querySelector("#ton-submit");
const tonRefreshButton = document.querySelector("#ton-refresh");

const state = {
  paymentConfig: null,
  tonConfig: null,
  activeSticker: null,
  activeInvoice: null,
  expiryTimer: null,
};

function getTelegramUser() {
  try {
    return tg?.initDataUnsafe?.user ?? null;
  } catch (error) {
    console.error("Unable to read Telegram user", error);
    return null;
  }
}

async function fetchStickers() {
  const response = await fetch(`${backendUrl}/stickers/`);
  if (!response.ok) {
    throw new Error("Failed to load stickers");
  }
  return response.json();
}

async function fetchPaymentConfig() {
  const response = await fetch(`${backendUrl}/payments/config`);
  if (!response.ok) {
    return null;
  }
  return response.json();
}

async function fetchTonConfig() {
  try {
    const response = await fetch(`${backendUrl}/payments/ton/config`);
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    return null;
  }
}

async function createCheckout(sticker, user) {
  const payload = {
    sticker_id: sticker.id,
    telegram_user_id: user?.id?.toString?.() ?? "unknown",
    email: user?.username ?? user?.usernames?.[0] ?? undefined,
  };

  const response = await fetch(`${backendUrl}/payments/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Unable to create checkout session");
  }

  return response.json();
}

async function createTonInvoice(sticker, user) {
  const payload = {
    sticker_id: sticker.id,
    telegram_user_id: user?.id?.toString?.() ?? "unknown",
    email: user?.username ?? user?.usernames?.[0] ?? undefined,
  };

  const response = await fetch(`${backendUrl}/payments/ton/invoice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Unable to create TON invoice");
  }

  return response.json();
}

async function confirmTonPayment(invoiceId, transactionHash) {
  const response = await fetch(`${backendUrl}/payments/ton/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invoice_id: invoiceId, transaction_hash: transactionHash }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Unable to confirm TON payment");
  }

  return response.json();
}

async function refreshTonInvoice(invoiceId) {
  const response = await fetch(`${backendUrl}/payments/ton/invoice/${invoiceId}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Unable to refresh invoice");
  }
  return response.json();
}

function formatPrice(sticker) {
  const currency = (sticker.currency || state.paymentConfig?.currency || "usd").toLowerCase();
  if (currency === "ton") {
    const tonAmountValue = sticker.price_cents / 1_000_000_000;
    return `${tonAmountValue.toFixed(3)} TON`;
  }
  const amount = sticker.price_cents / 100;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: (sticker.currency || state.paymentConfig?.currency || "USD").toUpperCase(),
    }).format(amount);
  } catch (error) {
    return `${amount.toFixed(2)} ${(sticker.currency || "USD").toUpperCase()}`;
  }
}

function resetTonInvoiceUI() {
  tonInvoiceSection.classList.add("hidden");
  tonStatus.textContent = "";
  tonStatus.classList.remove("error", "success");
  tonHashInput.value = "";
  tonSubmitButton.disabled = false;
  tonRefreshButton.disabled = false;
  tonHashInput.disabled = false;
  state.activeInvoice = null;
  if (state.expiryTimer) {
    clearInterval(state.expiryTimer);
    state.expiryTimer = null;
  }
}

function updateTonExpiry(expiresAt) {
  if (!expiresAt) {
    tonExpiry.textContent = "";
    return;
  }

  const expiryDate = new Date(expiresAt);

  function renderCountdown() {
    const now = new Date();
    const remaining = expiryDate.getTime() - now.getTime();
    if (remaining <= 0) {
      tonExpiry.textContent = "Expired";
      if (state.expiryTimer) {
        clearInterval(state.expiryTimer);
        state.expiryTimer = null;
      }
      return;
    }
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    tonExpiry.textContent = `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
  }

  renderCountdown();
  if (state.expiryTimer) {
    clearInterval(state.expiryTimer);
  }
  state.expiryTimer = setInterval(renderCountdown, 1000);
}

function showTonInvoice(invoice, sticker) {
  state.activeInvoice = invoice;
  tonInvoiceSection.classList.remove("hidden");
  tonWallet.textContent = invoice.wallet_address;
  const tonValue = invoice.amount_nanoton / 1_000_000_000;
  tonAmount.textContent = `${tonValue.toFixed(3)} TON (${invoice.amount_nanoton} nanotons)`;
  tonComment.textContent = invoice.comment;
  tonStatus.textContent = "Invoice generated. Awaiting payment.";
  tonStatus.classList.remove("error", "success");
  tonHashInput.value = "";
  tonSubmitButton.disabled = false;
  tonRefreshButton.disabled = false;
  tonHashInput.disabled = false;
  updateTonExpiry(invoice.expires_at);
  const currency = (sticker.currency || "ton").toUpperCase();
  modalSubtitle.textContent = `Send ${tonValue.toFixed(3)} ${currency} from your TON wallet.`;
}

function markTonConfirmed(invoice) {
  tonStatus.textContent = "Payment confirmed! Your sticker pack will unlock shortly.";
  tonStatus.classList.remove("error");
  tonStatus.classList.add("success");
  tonSubmitButton.disabled = true;
  tonRefreshButton.disabled = true;
  tonHashInput.disabled = true;
  if (state.expiryTimer) {
    clearInterval(state.expiryTimer);
    state.expiryTimer = null;
  }
}

function showModal(sticker) {
  state.activeSticker = sticker;
  document.body.classList.add("modal-open");
  modal.classList.remove("hidden");
  modalTitle.textContent = sticker.name;
  modalSubtitle.textContent = formatPrice(sticker);
  paymentOptions.innerHTML = "";
  resetTonInvoiceUI();

  const currency = (sticker.currency || state.paymentConfig?.currency || "usd").toLowerCase();
  const user = getTelegramUser();
  const stripeAvailable = state.paymentConfig !== null && currency !== "ton";
  const tonAvailable = currency === "ton" && state.tonConfig !== null;

  if (stripeAvailable) {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "payment-option";
    option.innerHTML = `
      <span class="label">Pay with card</span>
      <span class="hint">Secure checkout powered by Stripe.</span>
    `;
    option.addEventListener("click", async () => {
      option.disabled = true;
      option.classList.add("disabled");
      try {
        const { checkout_url } = await createCheckout(sticker, user);
        if (tg?.openInvoice) {
          tg.openInvoice(checkout_url);
        } else {
          window.open(checkout_url, "_blank");
        }
      } catch (error) {
        option.disabled = false;
        option.classList.remove("disabled");
        alert(error.message);
      }
    });
    paymentOptions.appendChild(option);
  }

  if (tonAvailable) {
    const tonOption = document.createElement("button");
    tonOption.type = "button";
    tonOption.className = "payment-option";
    tonOption.innerHTML = `
      <span class="label">Pay with TON</span>
      <span class="hint">Send a quick on-chain transfer to complete your order.</span>
    `;
    tonOption.addEventListener("click", async () => {
      tonOption.disabled = true;
      tonOption.classList.add("disabled");
      tonInvoiceSection.classList.remove("hidden");
      tonStatus.textContent = "Generating invoice...";
      tonStatus.classList.remove("error", "success");
      try {
        const invoice = await createTonInvoice(sticker, user);
        showTonInvoice(invoice, sticker);
        tonOption.disabled = false;
        tonOption.classList.remove("disabled");
      } catch (error) {
        tonStatus.textContent = error.message;
        tonStatus.classList.add("error");
        tonOption.disabled = false;
        tonOption.classList.remove("disabled");
      }
    });
    paymentOptions.appendChild(tonOption);
  }

  if (!stripeAvailable && !tonAvailable) {
    const message = document.createElement("p");
    message.className = "status error";
    message.textContent = "No payment methods are available for this sticker yet.";
    paymentOptions.appendChild(message);
  }
}

function closeModal() {
  modal.classList.add("hidden");
  document.body.classList.remove("modal-open");
  state.activeSticker = null;
  resetTonInvoiceUI();
  tonRefreshButton.disabled = false;
  tonHashInput.disabled = false;
}

function renderSticker(sticker) {
  const node = template.content.cloneNode(true);
  const element = node.querySelector(".sticker");
  node.querySelector(".name").textContent = sticker.name;
  node.querySelector(".description").textContent = sticker.description ?? "";
  const priceLabel = node.querySelector(".price");
  if (priceLabel) {
    priceLabel.textContent = formatPrice(sticker);
  }
  const img = node.querySelector(".preview");
  if (sticker.image_url) {
    img.src = `${backendUrl}${sticker.image_url}`;
  } else {
    img.classList.add("hidden");
  }
  const button = node.querySelector(".buy");
  button.textContent = "Choose payment";
  button.addEventListener("click", () => {
    showModal(sticker);
  });
  stickersContainer.appendChild(node);
}

function attachEventListeners() {
  modalClose.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal();
    }
  });

  tonSubmitButton.addEventListener("click", async () => {
    if (!state.activeInvoice) {
      tonStatus.textContent = "Generate an invoice first.";
      tonStatus.classList.add("error");
      return;
    }
    const txHash = tonHashInput.value.trim();
    if (!txHash) {
      tonStatus.textContent = "Enter the TON transaction hash.";
      tonStatus.classList.add("error");
      return;
    }
    tonSubmitButton.disabled = true;
    tonStatus.textContent = "Verifying payment on-chain...";
    tonStatus.classList.remove("error", "success");
    try {
      const invoice = await confirmTonPayment(state.activeInvoice.invoice_id ?? state.activeInvoice.id, txHash);
      showTonInvoice(invoice, state.activeSticker);
      markTonConfirmed(invoice);
    } catch (error) {
      tonStatus.textContent = error.message;
      tonStatus.classList.add("error");
      tonSubmitButton.disabled = false;
    }
  });

  tonRefreshButton.addEventListener("click", async () => {
    if (!state.activeInvoice) {
      tonStatus.textContent = "Generate an invoice first.";
      tonStatus.classList.add("error");
      return;
    }
    tonRefreshButton.disabled = true;
    tonStatus.textContent = "Checking invoice status...";
    tonStatus.classList.remove("error", "success");
    try {
      const invoice = await refreshTonInvoice(state.activeInvoice.invoice_id ?? state.activeInvoice.id);
      showTonInvoice(invoice, state.activeSticker);
      if (invoice.status === "confirmed") {
        markTonConfirmed(invoice);
      } else if (invoice.status === "expired") {
        tonStatus.textContent = "Invoice expired. Generate a new one to try again.";
        tonStatus.classList.add("error");
      } else {
        tonStatus.textContent = "Invoice is still pending.";
      }
    } catch (error) {
      tonStatus.textContent = error.message;
      tonStatus.classList.add("error");
    } finally {
      tonRefreshButton.disabled = false;
    }
  });

  tonInvoiceSection.addEventListener("click", async (event) => {
    const button = event.target.closest(".copy");
    if (!button) {
      return;
    }
    const targetId = button.getAttribute("data-copy-target");
    const target = document.getElementById(targetId);
    if (!target) {
      return;
    }
    try {
      await navigator.clipboard.writeText(target.textContent.trim());
      button.textContent = "Copied!";
      setTimeout(() => {
        button.textContent = "Copy";
      }, 1800);
    } catch (error) {
      tonStatus.textContent = "Unable to copy to clipboard.";
      tonStatus.classList.add("error");
    }
  });
}

async function bootstrap() {
  try {
    if (tg) {
      tg.ready();
      tg.expand();
    }

    const [stickers, paymentConfig, tonConfig] = await Promise.all([
      fetchStickers(),
      fetchPaymentConfig().catch(() => null),
      fetchTonConfig(),
    ]);

    state.paymentConfig = paymentConfig;
    state.tonConfig = tonConfig;

    if (!stickers.length) {
      emptySection.classList.remove("hidden");
      return;
    }

    stickers.forEach(renderSticker);
  } catch (error) {
    emptySection.textContent = error.message;
    emptySection.classList.remove("hidden");
  }
}

attachEventListeners();
bootstrap();
