const tg = window.Telegram?.WebApp;
const backendUrl = import.meta?.env?.VITE_API_URL ?? window.API_BASE_URL ?? "http://localhost:8000";

const stickersContainer = document.querySelector("#stickers");
const emptySection = document.querySelector("#empty");
const template = document.querySelector("#sticker-card");

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
    throw new Error("Unable to load payment configuration");
  }
  return response.json();
}

async function createCheckout(sticker, user) {
  const payload = {
    sticker_id: sticker.id,
    telegram_user_id: user?.id?.toString?.() ?? "unknown",
    email: user?.usernames?.[0] ?? undefined,
  };

  const response = await fetch(`${backendUrl}/payments/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail ?? "Unable to create checkout session");
  }

  return response.json();
}

function renderSticker(sticker) {
  const node = template.content.cloneNode(true);
  const element = node.querySelector(".sticker");
  node.querySelector(".name").textContent = sticker.name;
  node.querySelector(".description").textContent = sticker.description ?? "";
  const img = node.querySelector(".preview");
  if (sticker.image_url) {
    img.src = `${backendUrl}${sticker.image_url}`;
  } else {
    img.classList.add("hidden");
  }
  const button = node.querySelector(".buy");
  button.textContent = `Buy ${(sticker.price_cents / 100).toFixed(2)} ${
    sticker.currency?.toUpperCase?.() ?? "USD"
  }`;
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const user = tg?.initDataUnsafe?.user ?? {};
      const { checkout_url } = await createCheckout(sticker, user);
      if (tg?.openInvoice) {
        tg.openInvoice(checkout_url);
      } else {
        window.open(checkout_url, "_blank");
      }
    } catch (error) {
      alert(error.message);
      button.disabled = false;
    }
  });
  stickersContainer.appendChild(node);
}

async function bootstrap() {
  try {
    if (tg) {
      tg.ready();
      tg.expand();
    }
    const [stickers] = await Promise.all([fetchStickers(), fetchPaymentConfig()]);
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

bootstrap();
