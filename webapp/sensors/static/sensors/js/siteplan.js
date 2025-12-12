// ------------------------------------------------------------
// SitePlan v4.2
// ------------------------------------------------------------
const siteplanConfig = {
    debug: false
};

if (siteplanConfig.debug) console.log("🚀 [SitePlan v4.2] Loading...");

// Global state
const state = {
    mainMap: null,
    modalMap: null,
    modalMode: "view",
    showLabels: true,
    isDirty: false,
    locations: [],
    changed: [],
    imageBounds: null,
    dom: {}   // elements populated in init()
};

// ------------------------------------------------------------
// Initialize the system ONCE at page load
// ------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    if (siteplanConfig.debug) console.log("🚀 [SitePlan v4.2] Initializing SitePlan");

    state.dom.cardImageUrl = document.getElementById("siteplan-container-main")?.dataset.imageUrl;
    state.dom.modal = document.getElementById("siteplan-modal");
    state.dom.modalBody = state.dom.modal?.querySelector(".modal-body");
    state.dom.modalFooter = state.dom.modal?.querySelector(".modal-footer");
    state.dom.modalTitle = document.getElementById("siteplan-modal-title");

    if (siteplanConfig.debug) console.log("🔍 Modal BODY found:", state.dom.modalBody);

    loadLocations();
    initMainMap();

    // Recompute sizes on browser resize
    window.addEventListener("resize", () => {
        if (state.mainMap && state.imageBounds) {
            state.mainMap.invalidateSize();
        }
        resizeModalMap();
    });

    hookModalEvents();
});

// ------------------------------------------------------------
// Load location data from DOM (already in page, passed from Django)
// ------------------------------------------------------------
function loadLocations() {
    const json = document.getElementById("siteplan-data-json")?.textContent;
    if (!json) return;

    state.locations = JSON.parse(json);
    if (siteplanConfig.debug) console.log("🔷 Loaded locations:", state.locations.length);
}

// ------------------------------------------------------------
// Apply aspect ratio height dynamically
// ------------------------------------------------------------
function applyAspectRatio(wrapper, img) {
    if (!wrapper) return;
    const w = wrapper.offsetWidth;
    if (!w) return;

    const aspect = img.naturalHeight / img.naturalWidth;
    const h = Math.round(w * aspect);

    wrapper.style.height = `${h}px`;
    if (siteplanConfig.debug) console.log(`📐 Wrapper height set to ${h}px (aspect=${aspect})`);
}

// ------------------------------------------------------------
// Initialize the MAIN CARD MAP (non-modal)
// ------------------------------------------------------------
function initMainMap() {
    if (siteplanConfig.debug) console.log("🟩 initMainMap()");
    const container = document.getElementById("siteplan-container-main");
    if (!container) return;

    const wrapper = container.parentElement;
    const imageUrl = container.dataset.imageUrl;
    const img = new Image();

    img.onload = () => {
        if (siteplanConfig.debug) console.log("🖼️ Main image loaded:", img.width, img.height);

        applyAspectRatio(container, img);

        const w = img.width;
        const h = img.height;
        const bounds = [[0,0], [h, w]];
        state.imageBounds = bounds;

        state.mainMap = L.map(container, {
            crs: L.CRS.Simple,
            zoomControl: true,
            attributionControl: false
        });

        L.imageOverlay(imageUrl, bounds).addTo(state.mainMap);
        addMarkersToMap(state.mainMap, "view");

        setTimeout(() => {
            if (siteplanConfig.debug) console.log('⏰ Delayed map fit');
            state.mainMap.invalidateSize();
            state.mainMap.fitBounds(bounds, { padding: [20, 20] });
        }, 0);

        if (siteplanConfig.debug) console.log("🟩 Main map initialized");
    };

    img.src = imageUrl;
}

// ------------------------------------------------------------
// Initialize MODAL map (View or Edit mode)
// ------------------------------------------------------------
function initModalMap(mode) {
    if (siteplanConfig.debug) console.log("🟣 initModalMap():", mode);

    const wrapper = document.getElementById("siteplan-wrapper-modal");
    const container = document.getElementById("siteplan-container-modal");
    if (!wrapper || !container) {
        if (siteplanConfig.debug) console.error("❌ Missing modal wrapper/container");
        return;
    }

    const w = state.imageBounds[1][1];
    const h = state.imageBounds[1][0];
    const bounds = state.imageBounds;

    state.modalMap = L.map(container, {
        crs: L.CRS.Simple,
        zoomControl: true,
        attributionControl: false
    });

    L.imageOverlay(state.dom.cardImageUrl, bounds).addTo(state.modalMap);

    addMarkersToMap(state.modalMap, mode);
    state.modalMap.fitBounds(bounds);
    state.modalMap.invalidateSize();

    if (siteplanConfig.debug) console.log("🟣 Modal map initialized");
}

// ------------------------------------------------------------
// Add markers to a map
// ------------------------------------------------------------
function addMarkersToMap(map, mode) {
    const editable = mode === "edit";

    state.locations.forEach(loc => {
        if (loc.x_pos == null || loc.y_pos == null) return;
        const pxY = (loc.y_pos / 100) * state.imageBounds[1][0];
        const pxX = (loc.x_pos / 100) * state.imageBounds[1][1];

        const marker = L.marker([pxY, pxX], {
            draggable: editable
        }).addTo(map);

        marker.bindTooltip(loc.name, {
            permanent: state.showLabels,
            direction: "center",
            className: "siteplan-label"
        });

        if (editable) {
            marker.on("dragend", e => {
                const newX = (e.target.getLatLng().lng / state.imageBounds[1][1]) * 100;
                const newY = (e.target.getLatLng().lat / state.imageBounds[1][0]) * 100;
                loc.x_pos = parseFloat(newX.toFixed(2));
                loc.y_pos = parseFloat(newY.toFixed(2));
                state.isDirty = true;
                if (!state.changed.find(c => c.slug === loc.slug)) {
                    state.changed.push(loc);
                }
                if (siteplanConfig.debug) console.log("✏️ Marker moved:", loc);
            });
        }
    });
}

// ------------------------------------------------------------
// Modal lifecycle + height fix
// ------------------------------------------------------------
function hookModalEvents() {
    if (!state.dom.modal) return;

    state.dom.modal.addEventListener("shown.bs.modal", () => {
        if (siteplanConfig.debug) console.log("🔶 Modal visible, recomputing height");
        resizeModalMap();
    });

    state.dom.modal.addEventListener("hidden.bs.modal", () => {
        if (siteplanConfig.debug) console.log("🔻 Modal closed (cleanup)");
        state.modalMap = null;
        state.isDirty = false;
        state.dom.modalBody.innerHTML = "";
        state.dom.modalFooter.innerHTML = "";
    });
}

// ------------------------------------------------------------
// Open modal (View or Edit)
// ------------------------------------------------------------
function openModal(mode) {
    if (siteplanConfig.debug) console.log("🟣 openModal():", mode);
    state.modalMode = mode;
    state.showLabels = true;
    state.isDirty = false;
    state.changed = [];

    buildModalBody();
    buildModalFooter(mode);
    initModalMap(mode);

    const modal = bootstrap.Modal.getOrCreateInstance(state.dom.modal);
    modal.show();
}

// ------------------------------------------------------------
// Build modal body HTML dynamically
// ------------------------------------------------------------
function buildModalBody() {
    if (siteplanConfig.debug) console.log("🔵 buildModalBody()");
    state.dom.modalBody.innerHTML = `
        <div class="siteplan-wrapper bg-light" id="siteplan-wrapper-modal">
            <div id="siteplan-container-modal" style="width:100%;height:100%;"></div>
        </div>
    `;
}

// ------------------------------------------------------------
// Build modal footer (Cancel, Save, Label Toggle)
// ------------------------------------------------------------
function buildModalFooter(mode) {
    if (siteplanConfig.debug) console.log("🔵 buildModalFooter()");
    const isEdit = mode === "edit";

    state.dom.modalFooter.innerHTML = `
        <div class="d-flex justify-content-between w-100">
            <div>
                <label class="form-check-label">
                    <input type="checkbox" class="form-check-input" id="toggle-labels" checked> Show labels
                </label>
            </div>

            <div>
                ${isEdit ? `
                    <button class="btn btn-secondary me-2" data-bs-dismiss="modal">Cancel</button>
                    <button class="btn btn-primary" id="save-siteplan-btn">Save Changes</button>
                ` : `
                    <button class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                `}
            </div>
        </div>
    `;

    document.getElementById("toggle-labels").addEventListener("change", e => {
        state.showLabels = e.target.checked;
        refreshModalLabels();
    });

    if (isEdit) {
        document.getElementById("save-siteplan-btn").addEventListener("click", saveEdits);
    }
}

// ------------------------------------------------------------
// Refresh label visibility
// ------------------------------------------------------------
function refreshModalLabels() {
    document.querySelectorAll(".siteplan-label").forEach(label => {
        label.style.display = state.showLabels ? "block" : "none";
    });
}

function resizeModalMap() {
    if (!state.modalMap) return;
    if (siteplanConfig.debug) console.log("📐 Resizing modal map");
    const wrapper = document.getElementById("siteplan-wrapper-modal");
    if (!wrapper) return;

    const w = wrapper.offsetWidth;
    const aspect = state.imageBounds[1][0] / state.imageBounds[1][1];
    const h = Math.round(w * aspect);

    wrapper.style.height = `${h}px`;
    state.modalMap.invalidateSize();
    state.modalMap.fitBounds(state.imageBounds);
}


// ------------------------------------------------------------
// Save edits via POST
// ------------------------------------------------------------
function saveEdits() {
    if (!state.isDirty || state.changed.length === 0) {
        if (siteplanConfig.debug) console.log("💾 No changes to save.");
        bootstrap.Modal.getInstance(state.dom.modal).hide();
        return;
    }

    if (siteplanConfig.debug) console.log("💾 Saving edits...", state.changed);
    const placeSlug = document.getElementById("siteplan-container-main").dataset.placeSlug;
    const url = `/${placeSlug}/siteplan/update/`;

    window.utils.fetchWithCSRF(url, {
        method: "POST",
        body: JSON.stringify({ locations: state.changed }),
    })
    .then(data => {
        if (siteplanConfig.debug) console.log("💾 Save successful:", data);
        bootstrap.Modal.getInstance(state.dom.modal).hide();
        location.reload();
    })
    .catch(err => {
        if (siteplanConfig.debug) console.error("❌ Save error:", err)
    });
}

// ------------------------------------------------------------
// Export API to window for buttons
// ------------------------------------------------------------
window.openSitePlanView = () => openModal("view");
window.openSitePlanEdit = () => openModal("edit");
