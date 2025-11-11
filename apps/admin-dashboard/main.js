const backendUrl = window.API_BASE_URL ?? "http://localhost:8000";
const loginForm = document.querySelector("#login-form");
const uploadForm = document.querySelector("#upload-form");
const logoutButton = document.querySelector("#logout");
const stickerList = document.querySelector("#sticker-list");
const dashboard = document.querySelector("#dashboard");
const authSection = document.querySelector("#auth");
const statusBanner = document.querySelector("[data-status]");
const formTitle = document.querySelector("[data-form-title]");
const submitButton = document.querySelector("[data-submit]");
const cancelEditButton = document.querySelector("#cancel-edit");
const editingHint = document.querySelector("[data-editing-hint]");

let editingStickerId = null;

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearStatus();
  const data = new FormData(loginForm);
  const password = data.get("password");

  try {
    const response = await fetch(`${backendUrl}/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: "admin", password }).toString(),
    });

    if (!response.ok) {
      throw new Error("Invalid password");
    }

    const token = await response.json();
    localStorage.setItem("authToken", token.access_token);
    loginForm.reset();
    toggleDashboard(true);
    setStatus("Logged in successfully.", "success");
    await loadStickers();
  } catch (error) {
    setStatus(error.message, "error");
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = getToken();
  if (!token) {
    handleUnauthorized();
    return;
  }

  const elements = uploadForm.elements;
  const name = elements.namedItem("name").value.trim();
  const description = elements.namedItem("description").value.trim();
  const priceValue = parseInt(elements.namedItem("price_cents").value, 10);
  const currency = elements.namedItem("currency").value.trim() || "usd";
  const isActive = elements.namedItem("active").checked;

  if (!name) {
    setStatus("Name is required.", "error");
    return;
  }

  if (!Number.isInteger(priceValue) || priceValue <= 0) {
    setStatus("Price must be a positive whole number.", "error");
    return;
  }

  const isEditing = Boolean(editingStickerId);
  const formData = new FormData();
  formData.append("name", name);
  if (description || isEditing) {
    formData.append("description", description);
  }
  formData.append("price_cents", String(priceValue));
  formData.append("currency", currency.toLowerCase());
  formData.append("active", isActive ? "true" : "false");

  const imageInput = elements.namedItem("image");
  if (imageInput.files.length > 0) {
    formData.append("image", imageInput.files[0]);
  }

  const url = isEditing
    ? `${backendUrl}/stickers/${editingStickerId}`
    : `${backendUrl}/stickers/`;

  try {
    const response = await fetch(url, {
      method: isEditing ? "PATCH" : "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    if (response.status === 401 || response.status === 403) {
      handleUnauthorized();
      return;
    }

    if (!response.ok) {
      const error = await safeJson(response);
      throw new Error(error?.detail ?? "Unable to save sticker");
    }

    await response.json();
    setStatus(isEditing ? "Sticker updated successfully." : "Sticker created successfully.", "success");
    resetFormState();
    await loadStickers();
  } catch (error) {
    setStatus(error.message, "error");
  }
});

logoutButton.addEventListener("click", () => {
  localStorage.removeItem("authToken");
  resetFormState();
  toggleDashboard(false);
  setStatus("You have been logged out.", "info");
});

cancelEditButton.addEventListener("click", () => {
  resetFormState();
  setStatus("Edit cancelled.", "info");
});

async function loadStickers() {
  const token = getToken();
  if (!token) {
    return;
  }

  try {
    const response = await fetch(`${backendUrl}/stickers/?include_inactive=true`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.status === 401 || response.status === 403) {
      handleUnauthorized();
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to load stickers");
    }

    const stickers = await response.json();
    renderStickers(stickers);
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function renderStickers(stickers) {
  stickerList.innerHTML = "";

  if (stickers.length === 0) {
    const emptyState = document.createElement("li");
    emptyState.textContent = "No stickers yet. Create your first sticker above.";
    emptyState.classList.add("empty-state");
    stickerList.appendChild(emptyState);
    return;
  }

  stickers.forEach((sticker) => {
    const item = document.createElement("li");
    item.classList.toggle("inactive", !sticker.active);

    if (sticker.image_url) {
      const img = document.createElement("img");
      img.src = `${backendUrl}${sticker.image_url}`;
      img.alt = sticker.name;
      item.appendChild(img);
    }

    const info = document.createElement("div");
    info.classList.add("sticker-info");
    const price = (sticker.price_cents / 100).toFixed(2);
    const badge = document.createElement("span");
    badge.classList.add("badge");
    badge.textContent = sticker.active ? "Active" : "Inactive";
    if (!sticker.active) {
      badge.classList.add("inactive");
    }

    const nameEl = document.createElement("div");
    nameEl.classList.add("sticker-name");
    nameEl.textContent = sticker.name;
    info.appendChild(nameEl);

    if (sticker.description) {
      const descriptionEl = document.createElement("div");
      descriptionEl.classList.add("sticker-description");
      descriptionEl.textContent = sticker.description;
      info.appendChild(descriptionEl);
    }

    const priceEl = document.createElement("div");
    priceEl.classList.add("sticker-price");
    priceEl.textContent = `${price} ${sticker.currency.toUpperCase()}`;
    info.appendChild(priceEl);
    const badgeWrapper = document.createElement("div");
    badgeWrapper.classList.add("badge-wrapper");
    badgeWrapper.appendChild(badge);
    info.appendChild(badgeWrapper);
    item.appendChild(info);

    const actions = document.createElement("div");
    actions.classList.add("actions");

    const edit = document.createElement("button");
    edit.textContent = "Edit";
    edit.classList.add("secondary");
    edit.addEventListener("click", () => startEditSticker(sticker));
    actions.appendChild(edit);

    const toggle = document.createElement("button");
    toggle.textContent = sticker.active ? "Deactivate" : "Activate";
    toggle.classList.add("secondary");
    toggle.addEventListener("click", () => toggleSticker(sticker));
    actions.appendChild(toggle);

    const remove = document.createElement("button");
    remove.textContent = "Delete";
    remove.classList.add("danger");
    remove.addEventListener("click", () => deleteSticker(sticker));
    actions.appendChild(remove);

    item.appendChild(actions);
    stickerList.appendChild(item);
  });
}

async function toggleSticker(sticker) {
  const token = getToken();
  if (!token) {
    handleUnauthorized();
    return;
  }

  try {
    const response = await fetch(`${backendUrl}/stickers/${sticker.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ active: !sticker.active }),
    });

    if (response.status === 401 || response.status === 403) {
      handleUnauthorized();
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to update sticker");
    }

    await loadStickers();
    setStatus(`Sticker ${sticker.active ? "deactivated" : "activated"}.`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function deleteSticker(sticker) {
  const token = getToken();
  if (!token) {
    handleUnauthorized();
    return;
  }

  if (!window.confirm(`Delete ${sticker.name}? This cannot be undone.`)) {
    return;
  }

  try {
    const response = await fetch(`${backendUrl}/stickers/${sticker.id}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.status === 401 || response.status === 403) {
      handleUnauthorized();
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to delete sticker");
    }

    await loadStickers();
    setStatus("Sticker deleted.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function startEditSticker(sticker) {
  editingStickerId = sticker.id;
  formTitle.textContent = "Edit sticker";
  submitButton.textContent = "Update sticker";
  cancelEditButton.classList.remove("hidden");
  editingHint.classList.remove("hidden");

  const elements = uploadForm.elements;
  elements.namedItem("name").value = sticker.name;
  elements.namedItem("description").value = sticker.description ?? "";
  elements.namedItem("price_cents").value = sticker.price_cents;
  elements.namedItem("currency").value = sticker.currency;
  elements.namedItem("active").checked = Boolean(sticker.active);
  elements.namedItem("image").value = "";

  setStatus(`Editing “${sticker.name}”. Make changes and click Update sticker.`, "info");
}

function resetFormState() {
  editingStickerId = null;
  uploadForm.reset();
  formTitle.textContent = "Create sticker";
  submitButton.textContent = "Save sticker";
  cancelEditButton.classList.add("hidden");
  editingHint.classList.add("hidden");
}

function toggleDashboard(show) {
  if (show) {
    authSection.classList.add("hidden");
    dashboard.classList.remove("hidden");
  } else {
    authSection.classList.remove("hidden");
    dashboard.classList.add("hidden");
  }
}

function handleUnauthorized() {
  localStorage.removeItem("authToken");
  resetFormState();
  toggleDashboard(false);
  setStatus("Your session expired. Please log in again.", "error");
}

function getToken() {
  return localStorage.getItem("authToken");
}

function clearStatus() {
  if (!statusBanner) return;
  statusBanner.classList.add("hidden");
  statusBanner.textContent = "";
  statusBanner.classList.remove("success", "error", "info");
}

function setStatus(message, type = "info") {
  if (!statusBanner) return;
  statusBanner.textContent = message;
  statusBanner.classList.remove("hidden", "success", "error", "info");
  statusBanner.classList.add(type);
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return null;
  }
}

(function init() {
  const token = getToken();
  if (token) {
    toggleDashboard(true);
    loadStickers();
  }
})();
