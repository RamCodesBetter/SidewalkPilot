"use strict";

// Binary correction references are independent of the twelve-class proposal and reviews.
class MaskCorrections {
  constructor(hooks) {
    this.h = hooks; this.active = false; this.entries = new Map(); this.state = null;
    this.points = []; this.undoStack = []; this.redoStack = []; this.stroke = null;
    this.tool = "brush"; this.zoom = 1; this.key = ""; this.writes = Promise.resolve();
    this.dirty = false; this.change = 0; this.loadToken = 0; this.storageError = false;
    this.db = null; this.pan = null;
    const $ = hooks.$;
    $("edit-mode").onclick = () => this.toggle();
    document.querySelectorAll("[data-tool]").forEach(b => b.onclick = () => {
      if (this.points.length) { this.h.message("Finish or cancel the polygon first."); return; }
      this.tool = b.dataset.tool; this.controls(); this.h.canvas.focus();
    });
    $("polygon-finish").onclick = () => this.finishPolygon();
    $("polygon-cancel").onclick = () => { this.points = []; this.controls(); this.h.draw(); };
    $("edit-undo").onclick = () => this.undo(); $("edit-redo").onclick = () => this.redo();
    $("brush-size").oninput = () => { $("brush-value").textContent = $("brush-size").value + " px"; };
    $("zoom-in").onclick = () => this.setZoom(Math.min(8, this.zoom * 1.5));
    $("zoom-out").onclick = () => this.setZoom(Math.max(1, this.zoom / 1.5));
    $("zoom-fit").onclick = () => this.setZoom(1);
    $("edit-original").onchange = () => { if (this.points.length) this.points = []; this.controls(); this.h.draw(); };
    $("reference-ready").onchange = () => {
      if (!this.state) return;
      this.state.entry.status = $("reference-ready").checked ? "reviewed" : "draft";
      this.changed(false);
    };
    $("correction-notes").oninput = () => {
      if (!this.state) return;
      this.state.entry.notes = $("correction-notes").value; this.changed(false);
    };
    $("export-corrections").onclick = () => this.export().catch(e => hooks.message(e.message));
    $("import-corrections").onclick = () => $("correction-input").click();
    $("correction-input").onchange = async e => {
      const file = e.target.files[0]; if (!file) return;
      try { await this.import(JSON.parse(await file.text())); }
      catch (error) { hooks.message(error.message); }
      finally { e.target.value = ""; }
    };
    hooks.canvas.addEventListener("pointerdown", e => this.down(e));
    hooks.canvas.addEventListener("pointermove", e => this.move(e));
    for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) {
      hooks.canvas.addEventListener(name, () => this.endStroke());
    }
    hooks.canvas.addEventListener("dblclick", e => {
      if (this.active && this.tool === "polygon") { e.preventDefault(); this.finishPolygon(); }
    });
    addEventListener("beforeunload", e => { if (this.dirty || this.points.length || this.stroke) { e.preventDefault(); e.returnValue = ""; } });
  }
  async database() {
    if (this.db) return this.db;
    this.db = await new Promise((resolve, reject) => {
      const request = indexedDB.open("sidewalkpilot-pixel-corrections-v1", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("frames", {keyPath:"_key"}).createIndex("dataset", "dataset_key");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(Error("Correction storage is blocked by another tab"));
    });
    return this.db;
  }
  async configure(key) {
    await this.writes; this.key = key; this.entries = new Map(); this.state = null;
    this.storageError = false;
    try {
      const db = await this.database();
      const rows = await new Promise((resolve, reject) => {
        const request = db.transaction("frames").objectStore("frames").index("dataset").getAll(key);
        request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
      });
      for (const row of rows) if (this.h.names().includes(row.image)) this.entries.set(row.image, row);
    } catch { this.storageError = true; this.h.message("Correction storage unavailable. Export corrections before closing."); }
    this.controls();
  }
  reset() {
    this.loadToken++; this.state = null; this.active = false; this.points = [];
    this.h.$("edit-mode").disabled = true; this.setModeUI();
  }
  setModeUI() {
    document.body.classList.toggle("editing", this.active);
    this.h.$("edit-tools").hidden = !this.active; this.h.$("editor-panel").hidden = !this.active;
    this.h.$("edit-mode").setAttribute("aria-pressed", String(this.active));
    for (const id of ["export", "clear-reviews", "import"]) this.h.$(id).disabled = this.active || !this.h.names().length;
    this.h.canvas.style.width = this.active ? (this.zoom * 100) + "%" : "";
    this.controls();
  }
  async toggle() {
    if ((!this.active && !this.h.current()) || !this.canLeave()) return;
    this.active = !this.active; this.setModeUI();
    const list = this.h.visibleNames();
    const name = this.h.current()?.record.image || this.h.names()[this.h.index()];
    await this.h.show(this.h.names().indexOf(list.includes(name) ? name : list[0]));
  }
  canLeave() {
    this.endStroke();
    if (this.points.length) { this.h.message("Finish or cancel the polygon before changing images."); return false; }
    return true;
  }
  leave() { this.loadToken++; this.state = null; this.undoStack = []; this.redoStack = []; this.controls(); }
  async open(current) {
    const token = ++this.loadToken, record = current.record;
    const source = await this.h.file("images/" + record.image);
    if (await MaskCorrections.hash(new Uint8Array(await source.arrayBuffer())) !== record.source_sha256) throw Error("Original photo hash does not match");
    const originalMask = await this.h.file(record.mask);
    if (await MaskCorrections.hash(new Uint8Array(await originalMask.arrayBuffer())) !== record.mask_sha256) throw Error("Original mask hash does not match");
    const url = URL.createObjectURL(source);
    let image;
    try { image = new Image(); image.src = url; await image.decode(); }
    finally { URL.revokeObjectURL(url); }
    if (token !== this.loadToken) return;
    if (image.width !== record.size[0] || image.height !== record.size[1]) throw Error("Original photo dimensions differ");
    let entry = this.entries.get(record.image);
    if (entry) MaskCorrections.validateEntry(entry, record);
    else {
      const now = new Date().toISOString();
      entry = {image:record.image, size:[...record.size], source_sha256:record.source_sha256,
        base_mask_sha256:record.mask_sha256, pixels:Uint8Array.from(current.mask, id => id === 1 ? 1 : 0),
        status:"draft", notes:"", created_utc:now, updated_utc:now,
        seed:"Generated proposal: class 1 retained; all other IDs mapped to unverified non-sidewalk 0"};
      this.entries.set(record.image, entry);
    }
    this.state = {entry, image}; this.undoStack = []; this.redoStack = []; this.points = [];
    this.h.$("edit-original").checked = false; this.h.$("correction-notes").value = entry.notes;
    this.setZoom(1); this.controls();
  }
  static validateEntry(entry, record) {
    if (entry.image !== record.image || entry.source_sha256 !== record.source_sha256 || entry.base_mask_sha256 !== record.mask_sha256 || JSON.stringify(entry.size) !== JSON.stringify(record.size)) throw Error("Correction source or proposal hash does not match");
    if (!(entry.pixels instanceof Uint8Array) || entry.pixels.length !== record.size[0] * record.size[1] || entry.pixels.some(id => ![0,1,255].includes(id))) throw Error("Invalid correction pixels");
    if (!["draft","reviewed"].includes(entry.status) || typeof entry.notes !== "string" || !Number.isFinite(Date.parse(entry.updated_utc)) || !Number.isFinite(Date.parse(entry.created_utc)) || typeof entry.seed !== "string") throw Error("Invalid correction metadata");
  }
  save(entry) {
    const snapshot = {...entry, pixels:entry.pixels.slice(), _key:this.key + "|" + entry.image, dataset_key:this.key};
    this.h.$("correction-saved").textContent = "Saving local draft...";
    this.writes = this.writes.then(async () => {
      const db = await this.database();
      await new Promise((resolve, reject) => {
        const tx = db.transaction("frames", "readwrite");
        tx.objectStore("frames").put(snapshot); tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error); tx.onabort = () => reject(tx.error);
      });
      this.storageError = false;
    }).catch(() => { this.storageError = true; }).then(() => this.controls());
  }
  changed(pixels = true) {
    if (!this.state) return;
    if (pixels) this.state.entry.status = "draft";
    this.state.entry.updated_utc = new Date().toISOString(); this.dirty = true; this.change++;
    this.save(this.state.entry); this.controls(); this.h.draw();
  }
  controls() {
    const $ = this.h.$, ready = !!this.state;
    $("edit-undo").disabled = !ready || !(this.undoStack.length || this.points.length);
    $("edit-redo").disabled = !ready || !this.redoStack.length || !!this.points.length;
    $("polygon-finish").disabled = this.points.length < 3;
    $("polygon-cancel").disabled = !this.points.length;
    $("reference-ready").disabled = !ready || !!this.points.length || !!this.stroke;
    $("correction-notes").disabled = !ready;
    $("reference-ready").checked = ready && this.state.entry.status === "reviewed";
    $("export-corrections").disabled = !this.entries.size || !!this.points.length || !!this.stroke;
    $("import-corrections").disabled = !this.key;
    $("correction-status").textContent = !ready ? "No reference selected" : this.state.entry.status === "reviewed" ? "Reference checked" : "Draft reference";
    $("correction-saved").textContent = this.storageError ? "Local save unavailable. Export before closing." : this.dirty ? "Local draft only / export pending" : "Corrections stored separately";
    const rows = [...this.entries.values()];
    $("correction-count").textContent = rows.filter(e => e.status === "reviewed").length + " checked / " + rows.length + " reference drafts";
    document.querySelectorAll("[data-tool]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.tool === this.tool)));
    this.h.canvas.classList.toggle("pan-tool", this.active && this.tool === "pan");
  }
  label() { return this.tool === "eraser" ? 0 : Number(document.querySelector('input[name="paint-label"]:checked').value); }
  point(e) {
    const rect = this.h.canvas.getBoundingClientRect(), [w,h] = this.state.entry.size;
    return [Math.max(0, Math.min(w - .001, (e.clientX - rect.left) * w / rect.width)), Math.max(0, Math.min(h - .001, (e.clientY - rect.top) * h / rect.height))];
  }
  down(e) {
    if (!this.active || !this.state || e.button !== 0 || this.stroke || this.pan) return;
    e.preventDefault(); this.h.canvas.focus(); this.h.canvas.setPointerCapture(e.pointerId);
    if (this.tool === "pan") { this.pan = [e.clientX, e.clientY]; return; }
    if (this.h.$("edit-original").checked) { this.h.message("Switch off Original proposal before editing."); return; }
    const point = this.point(e);
    if (this.tool === "polygon") { if (e.detail < 2) this.points.push(point); this.controls(); this.h.draw(); return; }
    this.stroke = {before:this.state.entry.pixels.slice(), last:point, id:this.label()};
    this.stamp(point); this.controls(); this.h.draw();
  }
  stamp([x,y]) {
    const {pixels, size:[w,h]} = this.state.entry, radius = Number(this.h.$("brush-size").value) / 2;
    for (let row = Math.max(0, Math.floor(y-radius)); row < Math.min(h, Math.ceil(y+radius)); row++) {
      for (let col = Math.max(0, Math.floor(x-radius)); col < Math.min(w, Math.ceil(x+radius)); col++) {
        if ((col+.5-x)**2 + (row+.5-y)**2 <= radius**2) pixels[row*w+col] = this.stroke.id;
      }
    }
  }
  move(e) {
    if (this.pan) {
      const area = this.h.canvas.parentElement;
      area.scrollLeft -= e.clientX-this.pan[0]; area.scrollTop -= e.clientY-this.pan[1]; this.pan = [e.clientX,e.clientY]; return;
    }
    if (!this.stroke || !this.state) return;
    const end = this.point(e), start = this.stroke.last;
    const steps = Math.max(1, Math.ceil(Math.hypot(end[0]-start[0],end[1]-start[1]) / Math.max(1,Number(this.h.$("brush-size").value)/4)));
    for (let i=1;i<=steps;i++) this.stamp([start[0]+(end[0]-start[0])*i/steps, start[1]+(end[1]-start[1])*i/steps]);
    this.stroke.last = end; this.h.draw();
  }
  endStroke() {
    this.pan = null;
    if (!this.stroke || !this.state) return;
    const before = this.stroke.before; this.stroke = null;
    this.commit(before);
  }
  commit(before) {
    if (before.some((value, i) => value !== this.state.entry.pixels[i])) {
      this.undoStack.push(before); if (this.undoStack.length > 32) this.undoStack.shift();
      this.redoStack = []; this.changed();
    } else this.controls();
  }
  finishPolygon() {
    if (!this.state || this.points.length < 3 || this.h.$("edit-original").checked) return;
    const {pixels,size:[w,h]} = this.state.entry, before = pixels.slice(), id = this.label(), points = this.points;
    // Even-odd fill at pixel centers: exports contain hard IDs, never antialias colors.
    for (let y=Math.max(0,Math.floor(Math.min(...points.map(p=>p[1])))); y<Math.min(h,Math.ceil(Math.max(...points.map(p=>p[1])))); y++) {
      const xs = [];
      for (let i=0,j=points.length-1;i<points.length;j=i++) {
        const [ax,ay]=points[j], [bx,by]=points[i];
        if ((ay>y+.5)!==(by>y+.5)) xs.push(ax+(y+.5-ay)*(bx-ax)/(by-ay));
      }
      xs.sort((a,b)=>a-b);
      for (let i=0;i+1<xs.length;i+=2) for (let x=Math.max(0,Math.ceil(xs[i]-.5));x<Math.min(w,Math.ceil(xs[i+1]-.5));x++) pixels[y*w+x]=id;
    }
    this.points=[]; this.commit(before); this.h.draw();
  }
  undo() {
    if (this.points.length) { this.points.pop(); this.controls(); this.h.draw(); return; }
    if (!this.state || !this.undoStack.length || this.stroke) return;
    this.redoStack.push(this.state.entry.pixels); this.state.entry.pixels=this.undoStack.pop(); this.changed();
  }
  redo() {
    if (!this.state || !this.redoStack.length || this.points.length || this.stroke) return;
    this.undoStack.push(this.state.entry.pixels); this.state.entry.pixels=this.redoStack.pop(); this.changed();
  }
  setZoom(value) {
    const area=this.h.canvas.parentElement, ratio=value/this.zoom;
    const x=(area.scrollLeft+area.clientWidth/2)*ratio-area.clientWidth/2;
    const y=(area.scrollTop+area.clientHeight/2)*ratio-area.clientHeight/2;
    this.zoom=value; this.h.canvas.style.width=this.active ? value*100+"%" : "";
    area.scrollLeft=x; area.scrollTop=y; this.h.$("zoom-value").textContent=Math.round(value*100)+"%";
  }
  draw(ctx, mode) {
    if (!this.state) return;
    const {entry,image}=this.state, [w,h]=entry.size, canvas=this.h.canvas;
    canvas.width=w; canvas.height=h; ctx.drawImage(image,0,0,w,h);
    const original=this.h.$("edit-original").checked;
    const mask=original ? this.h.current().mask : entry.pixels;
    if (mode!=="source") {
      const pixels=ctx.getImageData(0,0,w,h), opacity=Number(this.h.$("opacity").value)/100;
      for (let i=0;i<mask.length;i++) {
        const id=original ? (mask[i]===1?1:0) : mask[i];
        const color=id===1?[50,197,144]:id===255?[237,182,73]:[38,43,48];
        const alpha=mode==="mask"?1:id===0?0:id===255?((i%w+Math.floor(i/w))%12<5?.7:.2):opacity;
        for(let c=0;c<3;c++) pixels.data[i*4+c]=Math.round(pixels.data[i*4+c]*(1-alpha)+color[c]*alpha);
      }
      ctx.putImageData(pixels,0,0);
    }
    if(this.points.length) {
      ctx.beginPath(); this.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
      ctx.strokeStyle="#f8e565";ctx.lineWidth=3/this.zoom;ctx.stroke();
      for(const [x,y] of this.points){ctx.beginPath();ctx.arc(x,y,4/this.zoom,0,Math.PI*2);ctx.fillStyle="#f8e565";ctx.fill();}
    }
  }
  keydown(e) {
    if (!this.active) return false;
    const target=e.target;
    if(target.isContentEditable||target.closest("textarea")||(target.tagName==="INPUT"&&!["radio","range","checkbox"].includes(target.type)))return false;
    const key=e.key.toLowerCase();
    if ((e.ctrlKey||e.metaKey)&&["z","y"].includes(key)) {
      e.preventDefault();if(!e.repeat)(key==="y"||e.shiftKey?this.redo():this.undo());return true;
    }
    if(e.ctrlKey||e.metaKey||e.altKey)return false;
    const action={Digit1:"1",Digit2:"2",Digit3:"3",Numpad1:"1",Numpad2:"2",Numpad3:"3"}[e.code]||e.key;
    if(["1","2","3"].includes(action)) {
      e.preventDefault();document.querySelector(`input[name="paint-label"][value="${{"1":1,"2":0,"3":255}[action]}"]`).checked=true;
      if(this.tool==="eraser")this.tool="brush";this.controls();return true;
    }
    if(e.key==="Escape") {e.preventDefault();this.points=[];this.controls();this.h.draw();this.h.canvas.focus();return true;}
    if(e.key==="Enter"&&this.points.length){e.preventDefault();if(!e.repeat)this.finishPolygon();return true;}
    return false;
  }
  static async hash(bytes) {
    return [...new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))].map(b=>b.toString(16).padStart(2,"0")).join("");
  }
  static encode(pixels) {
    const runs=[]; for(let i=0;i<pixels.length;){const id=pixels[i];let end=i+1;while(end<pixels.length&&pixels[end]===id)end++;runs.push(id,end-i);i=end;}return runs;
  }
  static decode(runs,size) {
    if(!Array.isArray(runs)||!runs.length||runs.length%2||runs.length>size*2)throw Error("Invalid pixel runs");
    const pixels=new Uint8Array(size);let offset=0;
    for(let i=0;i<runs.length;i+=2){const id=runs[i],count=runs[i+1];if(![0,1,255].includes(id)||!Number.isSafeInteger(count)||count<=0||offset+count>size)throw Error("Invalid pixel runs");pixels.fill(id,offset,offset+count);offset+=count;}
    if(offset!==size)throw Error("Incomplete pixel runs");return pixels;
  }
  async export() {
    if(!this.canLeave())return;
    await this.writes;
    const change=this.change, key=this.key, entries=[...this.entries.values()].map(e=>({...e,pixels:e.pixels.slice()})), rows=[];
    for(const entry of entries){const {_key,dataset_key,pixels,...meta}=entry;rows.push({...meta,pixels_sha256:await MaskCorrections.hash(pixels),pixels_rle:MaskCorrections.encode(pixels)});}
    const value={schema:"sidewalkpilot-class1-corrections-v1",dataset_key:key,exported_utc:new Date().toISOString(),
      encoding:"row-major uint8; alternating [value, count] runs",labels:{"0":"non-sidewalk (binary reference only)","1":"sidewalk/path","255":"uncertain / excluded from evaluation"},
      annotation_scope:{kind:"binary_class_reference",positive_class_id:1,not_a_12_class_mask:true},
      authorship:"Human corrections initialized from generated proposals; draft entries are not verified references",entries:rows};
    const url=URL.createObjectURL(new Blob([JSON.stringify(value)],{type:"application/json"})),a=document.createElement("a");
    a.href=url;a.download="sidewalkpilot-class-1-corrections.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    if(this.change===change&&this.key===key)this.dirty=false;this.controls();this.h.message("Corrections exported separately. Original masks unchanged.");
  }
  async import(value) {
    if(!this.canLeave())return;
    const key=this.key,change=this.change,token=this.loadToken;
    if(value.schema!=="sidewalkpilot-class1-corrections-v1"||value.dataset_key!==key||value.annotation_scope?.kind!=="binary_class_reference"||value.annotation_scope.positive_class_id!==1||!Array.isArray(value.entries)||value.entries.length>this.h.names().length)throw Error("Correction file does not match this dataset");
    const incoming=new Map();
    for(const row of value.entries){
      if(!this.h.names().includes(row.image)||incoming.has(row.image))throw Error("Unknown or duplicate correction image");
      const record=await this.h.record(row.image),pixels=MaskCorrections.decode(row.pixels_rle,record.size[0]*record.size[1]);
      const entry={image:row.image,size:row.size,source_sha256:row.source_sha256,base_mask_sha256:row.base_mask_sha256,pixels,status:row.status,notes:row.notes,created_utc:row.created_utc,updated_utc:row.updated_utc,seed:row.seed};
      MaskCorrections.validateEntry(entry,record);if(await MaskCorrections.hash(pixels)!==row.pixels_sha256)throw Error("Correction pixel hash does not match");incoming.set(row.image,entry);
    }
    if(key!==this.key||change!==this.change||token!==this.loadToken)throw Error("View changed during import; retry");
    if([...incoming.keys()].some(n=>this.entries.has(n))&&!confirm("Replace local correction drafts for the imported images? Original masks and reviews remain unchanged."))return;
    for(const [name,entry] of incoming){this.entries.set(name,entry);this.save(entry);}this.change++;this.dirty=true;
    await this.h.show(this.h.index());this.h.message("Corrections imported. Original masks and reviews unchanged.");
  }
}
