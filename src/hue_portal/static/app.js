"use strict";
const $ = id => document.getElementById(id);
const channels = ["rectangle_front_left", "rectangle_front_right", "rectangle_rear_left", "rectangle_rear_right", "bedside"];
let token = "", library, editing = null;
const message = text => { $("message").textContent = text; };
async function api(path, method = "GET", body) {
  const response = await fetch(`/api/${path}`, {method, headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Invalid library. Check fields, ranges, scene references and duplicate event names.");
  return data;
}
function action(id, fn) { $(id).onclick = async () => { $(id).disabled = true; try { await fn(); } catch (e) { message(e.message); } finally { $(id).disabled = false; } }; }
function element(tag, text, className) { const node = document.createElement(tag); if (text) node.textContent = text; if (className) node.className = className; return node; }
function refresh() {
  const previous = $("game").value;
  $("game").replaceChildren(new Option("All presets", ""));
  Object.entries(library.games).forEach(([id, game]) => $("game").add(new Option(game.name, id)));
  $("game").value = library.games[previous] ? previous : "";
  $("libraryJson").value = JSON.stringify(library, null, 2);
  render();
}
async function reload() { library = await api("library"); refresh(); message(`Connected · library revision ${library.revision}`); }
async function save(candidate) { library = await api("library", "PUT", candidate); refresh(); message(`Saved on Pi · revision ${library.revision}. Game clients use updates on their next session.`); }
function render() {
  const game = library.games[$("game").value];
  const ids = game ? new Set(Object.values(game.events).map(e => e.scene)) : null;
  $("presets").replaceChildren();
  for (const [id, scene] of Object.entries(library.scenes)) {
    if ((ids && !ids.has(id)) || !`${id} ${scene.name}`.toLowerCase().includes($("search").value.toLowerCase())) continue;
    const card = element("article", null, "card"), swatches = element("div", null, "swatches");
    channels.forEach(c => { const swatch = element("input"); swatch.type = "color"; swatch.value = scene.lights[c].palette[0]; swatch.tabIndex = -1; swatch.setAttribute("aria-label", `${c}: ${swatch.value}`); swatches.append(swatch); });
    card.append(swatches, element("h3", scene.name), element("p", `${scene.motion} · ${id}`));
    const row = element("div", null, "row"), play = element("button", "Play"), edit = element("button", "Edit", "secondary");
    play.onclick = async () => { play.disabled = true; try { await api("play", "POST", {scene: id, ambient: $("ambient").checked, lighting: {brightness: Number($("brightness").value) / 100}}); message(`Playing ${scene.name}`); await status(); } catch (e) { message(e.message); } finally { play.disabled = false; } };
    edit.onclick = () => editScene(id);
    row.append(play, edit); card.append(row); $("presets").append(card);
  }
}
function editScene(id) {
  editing = id;
  const scene = id ? library.scenes[id] : {name: "New preset", motion: "ambient", effect: "default", transition_seconds: 4, lights: Object.fromEntries(channels.map(c => [c, {palette: ["#628D50"], brightness: [20, 35]}]))};
  $("sceneId").value = id || ""; $("sceneId").disabled = !!id;
  $("sceneName").value = scene.name; $("motion").value = scene.motion; $("effect").value = scene.effect; $("transition").value = scene.transition_seconds;
  $("channels").replaceChildren();
  for (const c of channels) {
    const section = element("div", null, "channel"), row = element("div", null, "row"); section.append(element("h3", c.replaceAll("_", " ")));
    for (const [key, title, value] of [["palette", "Colors (comma separated hex)", scene.lights[c].palette.join(", ")], ["low", "Minimum brightness", scene.lights[c].brightness[0]], ["high", "Maximum brightness", scene.lights[c].brightness[1]], ["interval", "Timing seconds (optional min, max)", (scene.lights[c].interval_seconds || []).join(", ")]]) {
      const label = element("label", title), input = element("input"); input.id = `${c}_${key}`; input.value = value; if (["low", "high"].includes(key)) { input.type = "number"; input.min = 0; input.max = 100; input.step = "0.1"; } label.append(input); row.append(label);
    } section.append(row); $("channels").append(section);
  }
  $("deleteScene").hidden = $("duplicate").hidden = !id;
  $("editor").hidden = false; $("editor").scrollIntoView({behavior: "smooth"});
}
action("connect", async () => { token = $("token").value; await reload(); $("token").value = ""; $("login").hidden = true; $("portal").hidden = false; await status(); });
action("saveScene", async () => {
  const id = $("sceneId").value.trim(); if (!/^[a-z][a-z0-9_]*$/.test(id)) throw new Error("Use lowercase letters, numbers and underscores for the ID.");
  if (!editing && library.scenes[id]) throw new Error("That preset ID already exists.");
  const candidate = structuredClone(library), lights = {};
  for (const c of channels) lights[c] = {palette: $(`${c}_palette`).value.split(",").map(s => s.trim()), brightness: [Number($(`${c}_low`).value), Number($(`${c}_high`).value)], interval_seconds: $(`${c}_interval`).value.trim() ? $(`${c}_interval`).value.split(",").map(Number) : null};
  candidate.scenes[id] = {name: $("sceneName").value, motion: $("motion").value, effect: $("effect").value, transition_seconds: Number($("transition").value), lights};
  await save(candidate); editScene(id);
});
action("duplicate", () => { editing = null; $("sceneId").disabled = false; $("sceneId").value += "_copy"; $("sceneName").value += " (copy)"; $("deleteScene").hidden = $("duplicate").hidden = true; });
action("deleteScene", async () => {
  if (Object.values(library.games).some(g => Object.values(g.events).some(e => e.scene === editing))) throw new Error("Remove or redirect game mappings for this preset before deleting it.");
  if (!confirm("Delete this preset from the Pi?")) return;
  const candidate = structuredClone(library); delete candidate.scenes[editing]; await save(candidate); $("editor").hidden = true;
});
action("newScene", () => editScene(null)); action("cancelEdit", () => { $("editor").hidden = true; });
action("saveLibrary", async () => { await save(JSON.parse($("libraryJson").value)); $("editor").hidden = true; });
action("reload", async () => { await reload(); $("editor").hidden = true; });
action("download", () => { const url = URL.createObjectURL(new Blob([JSON.stringify(library, null, 2)], {type: "application/json"})); const a = element("a"); a.href = url; a.download = `hue-library-${library.revision}.json`; a.click(); URL.revokeObjectURL(url); });
action("stop", async () => { await api("stop", "POST"); message("Pi playback stopped. Lights retain their current state."); await status(); });
async function status() { const s = await api("status"); $("playback").textContent = s.error || (s.scene ? `${s.ambient ? "Ambient playback" : "Scene applied"}: ${library.scenes[s.scene]?.name || s.scene}` : "Pi playback stopped"); }
action("loadLights", async () => { const data = await api("lights"); $("mapping").replaceChildren(); for (const c of channels) { const label = element("label", c.replaceAll("_", " ")), select = element("select"); select.id = `map_${c}`; select.add(new Option("Choose a light", "")); data.resources.filter(r => r.dimming).forEach(r => select.add(new Option(r.metadata?.name || r.id, r.id))); select.value = data.mapping[c] || ""; label.append(select); $("mapping").append(label); } $("saveMapping").hidden = false; });
action("saveMapping", async () => { await api("mapping", "PUT", Object.fromEntries(channels.map(c => [c, $(`map_${c}`).value]))); message("Pi light positions saved. Pi playback stopped."); await status(); });
$("game").onchange = render; $("search").oninput = render;
$("brightness").oninput = () => { $("brightnessValue").textContent = $("brightness").value + "%"; };
setInterval(() => { if (library) status().catch(e => { $("playback").textContent = e.message; }); }, 10000);
