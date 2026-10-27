"""EZ-FEA desktop. One-screen native STEP analysis, no duplicate demo solver.

Open part -> hold face -> loaded face -> force -> SOLVE -> results.
Advanced material and mesh options remain accessible but out of the way.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ezfea.mesh import inspect_step
from ezfea.desktop_view import FacePicker
from ezfea.fixture_suggestions import check_hints
import hashlib
from ezfea.desktop_controller import (
    build_analysis, build_multi_analysis, open_result_folder, preflight, run_native_child_process,
)
from ezfea.desktop_presentation import PALETTE, DIRECTIONS, force_components, brief_native_result

C=PALETTE


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EZ-FEA | Structural Analysis")
        self.geometry("1040x755")
        self.minsize(805,650)
        self.configure(bg=C["background"])
        self.responses=queue.Queue()
        self.filename=""
        self.source_sha256=None
        self.active_run_signature=None
        self.faces=[]
        self.support_faces=[]
        self.suggested_support_faces=set()
        self.suggestions_review_pending=False
        self.busy=False
        self.latest=None

        self.fixed=tk.StringVar()
        self.loaded=tk.StringVar()
        self.force=tk.StringVar(value="100")
        self.direction=tk.StringVar(value=DIRECTIONS[0])
        self.mesh=tk.StringVar(value="7")
        self.fx=tk.StringVar(value="0")
        self.fy=tk.StringVar(value="-100")
        self.fz=tk.StringVar(value="0")
        self.e=tk.StringVar(value="200000")
        self.nu=tk.StringVar(value="0.26")
        self.yield_mpa=tk.StringVar(value="250")
        self.element_type=tk.StringVar(value="C3D10")
        self.status=tk.StringVar(value="Open a STEP part or choose the example.")
        self.part_name=tk.StringVar(value="No part loaded")
        self.part_detail=tk.StringVar(value="Real solid STEP geometry  •  N / mm / MPa")
        self.advanced_open=False
        self.activity_open=False
        self.result_vars={
            key:tk.StringVar(value="—")
            for key in ("headline","max_displacement","max_stress",
                        "yield_ratio","force_balance","moment_balance",
                        "elements","element_type")
        }
        self._styles()
        self._build()
        # A completed result belongs to the exact input settings used to
        # create it. Changing a load or material must never leave "SOLVED"
        # beside numbers for the previous setup.
        self._watched_inputs=(
            self.force,self.direction,self.mesh,self.e,self.nu,
            self.yield_mpa,self.element_type,self.loaded,
        )
        for field in self._watched_inputs:
            field.trace_add("write",lambda *_args:self._inputs_changed())
        self.after(150,self._poll)
        missing=preflight()
        self._log("Native solver detected." if not missing else
                  "Solver setup: "+" | ".join(missing))

    def _styles(self):
        style=ttk.Style(self)
        if "clam" in style.theme_names():style.theme_use("clam")
        style.configure(".",background=C["background"],foreground=C["text"],
                        font=("Segoe UI",10))
        style.configure("TFrame",background=C["background"])
        style.configure("Panel.TFrame",background=C["panel"])
        style.configure("TLabel",background=C["background"],foreground=C["text"])
        style.configure("Panel.TLabel",background=C["panel"],foreground=C["text"])
        style.configure("Muted.TLabel",background=C["background"],foreground=C["muted"])
        style.configure("PanelMuted.TLabel",background=C["panel"],foreground=C["muted"])
        style.configure("Brand.TLabel",background=C["background"],foreground=C["text"],
                        font=("Segoe UI",27,"bold"))
        style.configure("Large.TLabel",background=C["panel"],foreground=C["text"],
                        font=("Segoe UI",13,"bold"))
        style.configure("Metric.TLabel",background=C["panel"],foreground=C["accent"],
                        font=("Segoe UI",20,"bold"))
        style.configure("PanelTitle.TLabel",background=C["panel"],foreground=C["text"],
                        font=("Segoe UI",11,"bold"))
        style.configure("Accent.TButton",background=C["accent"],foreground=C["background"],
                        bordercolor=C["accent"],focuscolor=C["accent"],
                        font=("Segoe UI",13,"bold"),padding=(28,14))
        style.map("Accent.TButton",
                  background=[("disabled",C["border"]),("active",C["accent_hover"])],
                  foreground=[("disabled",C["muted"]),("active",C["background"])])
        style.configure("Quiet.TButton",background=C["panel_high"],foreground=C["text"],
                        bordercolor=C["border"],font=("Segoe UI",10,"bold"),
                        padding=(14,9))
        style.map("Quiet.TButton",background=[("active",C["border"])])
        style.configure("TEntry",fieldbackground=C["panel_high"],foreground=C["text"],
                        insertcolor=C["text"],bordercolor=C["border"],padding=9)
        style.configure("TCombobox",fieldbackground=C["panel_high"],background=C["panel_high"],
                        foreground=C["text"],arrowcolor=C["accent"],
                        bordercolor=C["border"],padding=8)
        style.map("TCombobox",fieldbackground=[("readonly",C["panel_high"])],
                  foreground=[("readonly",C["text"])],
                  selectbackground=[("readonly",C["panel_high"])],
                  selectforeground=[("readonly",C["text"])])
        self.option_add("*TCombobox*Listbox.background",C["panel_high"])
        self.option_add("*TCombobox*Listbox.foreground",C["text"])
        self.option_add("*TCombobox*Listbox.selectBackground",C["border"])
        self.option_add("*TCombobox*Listbox.selectForeground",C["accent"])

    def _panel(self,parent,padx=18,pady=15):
        frame=tk.Frame(parent,bg=C["panel"],highlightthickness=1,
                       highlightbackground=C["border"],padx=padx,pady=pady)
        frame.pack(fill="x",pady=(0,12))
        return frame

    def _label(self,parent,text,muted=False,bold=False):
        return tk.Label(parent,text=text,bg=C["panel"],
                        fg=C["muted"] if muted else C["text"],
                        font=("Segoe UI",10,"bold" if bold else "normal"),
                        anchor="w")

    def _build(self):
        root=tk.Frame(self,bg=C["background"],padx=23,pady=16)
        root.pack(fill="both",expand=True)

        head=tk.Frame(root,bg=C["background"])
        head.pack(fill="x",pady=(0,14))
        brand=tk.Frame(head,bg=C["background"])
        brand.pack(side="left")
        ttk.Label(brand,text="EZ-FEA",style="Brand.TLabel").pack(anchor="w")
        ttk.Label(brand,text="REAL 3D ANALYSIS, WITHOUT THE CLUTTER",
                  style="Muted.TLabel").pack(anchor="w")
        tk.Label(head,text="NATIVE 3D  •  BETA",bg=C["panel_high"],fg=C["accent"],
                 font=("Segoe UI",9,"bold"),padx=12,pady=7).pack(side="right",anchor="n",pady=7)

        source=self._panel(root)
        bar=tk.Frame(source,bg=C["panel"])
        bar.pack(fill="x")
        self.open_button=ttk.Button(bar,text="Open STEP",style="Quiet.TButton",command=self.open_file)
        self.open_button.pack(side="left")
        self.demo_button=ttk.Button(bar,text="Use example",style="Quiet.TButton",command=self.demo)
        self.demo_button.pack(side="left",padx=8)
        ttk.Label(source,textvariable=self.part_name,style="Large.TLabel").pack(anchor="w",pady=(14,2))
        ttk.Label(source,textvariable=self.part_detail,style="PanelMuted.TLabel").pack(anchor="w")

        workspace=tk.Frame(root,bg=C["background"])
        workspace.pack(fill="both",expand=True)
        self.picker=FacePicker(workspace,self._on_face_click,self._on_fixture_hints)
        self.picker.pack(side="left",fill="both",expand=True,padx=(0,12),pady=(0,8))
        right=tk.Frame(workspace,bg=C["background"])
        right.pack(side="right",fill="both",expand=True)
        setup=self._panel(right)
        title=tk.Frame(setup,bg=C["panel"])
        title.pack(fill="x",pady=(0,12))
        ttk.Label(title,text="SETUP",style="PanelTitle.TLabel").pack(side="left")
        tk.Label(title,text="1 / 2",bg=C["panel"],fg=C["muted"],
                 font=("Segoe UI",9)).pack(side="right")
        tk.Label(setup,text="Click the real 3D faces on the left.",bg=C["panel"],
                 fg=C["muted"],font=("Segoe UI",9)).pack(anchor="w",pady=(0,8))
        force_row=tk.Frame(setup,bg=C["panel"])
        force_row.pack(fill="x")
        force_row.columnconfigure(0,weight=1)
        force_row.columnconfigure(1,weight=2)
        self._label(force_row,"Force (N)",bold=True).grid(row=0,column=0,sticky="w",padx=(0,9))
        self._label(force_row,"Direction",bold=True).grid(row=0,column=1,sticky="w")
        ttk.Entry(force_row,textvariable=self.force).grid(row=1,column=0,sticky="ew",padx=(0,9),pady=(5,0))
        ttk.Combobox(force_row,textvariable=self.direction,values=DIRECTIONS,
                     state="readonly").grid(row=1,column=1,sticky="ew",pady=(5,0))
        ttk.Label(setup,text="Select actual CAD faces. The entire chosen face receives the force.",
                  style="PanelMuted.TLabel").pack(anchor="w",pady=(10,0))

        advanced=tk.Frame(right,bg=C["background"])
        advanced.pack(fill="x",pady=(0,12))
        self.advanced_button=ttk.Button(advanced,text="More settings  ▾",
                                        style="Quiet.TButton",command=self.toggle_advanced)
        self.advanced_button.pack(anchor="w")
        self.advanced_frame=tk.Frame(advanced,bg=C["panel"],padx=15,pady=12,
                                     highlightthickness=1,highlightbackground=C["border"])
        grid=tk.Frame(self.advanced_frame,bg=C["panel"])
        grid.pack(fill="x")
        settings=[
            ("Mesh size (mm)",self.mesh),("Young's E (MPa)",self.e),
            ("Poisson ratio",self.nu),("Yield (MPa)",self.yield_mpa),
        ]
        for i,(label,var) in enumerate(settings):
            cell=tk.Frame(grid,bg=C["panel"])
            cell.grid(row=i//2,column=i%2,sticky="ew",padx=(0,12),pady=5)
            self._label(cell,label).pack(anchor="w")
            ttk.Entry(cell,textvariable=var).pack(fill="x",pady=(4,0))
        for i in range(2):grid.grid_columnconfigure(i,weight=1)
        row=tk.Frame(self.advanced_frame,bg=C["panel"])
        row.pack(fill="x",pady=(7,0))
        self._label(row,"Element mesh").pack(side="left")
        ttk.Combobox(row,textvariable=self.element_type,values=("C3D10","C3D4"),
                     state="readonly",width=10).pack(side="left",padx=13)
        self._label(row,"C3D10 recommended for bending",muted=True).pack(side="left")
        self._label(self.advanced_frame,"Face ID fallback",muted=True).pack(anchor="w",pady=(10,4))
        fallback=tk.Frame(self.advanced_frame,bg=C["panel"])
        fallback.pack(fill="x")
        self.fix_box=ttk.Combobox(fallback,textvariable=self.fixed,state="readonly",width=15)
        self.fix_box.pack(side="left",fill="x",expand=True,padx=(0,4))
        self.load_box=ttk.Combobox(fallback,textvariable=self.loaded,state="readonly",width=15)
        self.load_box.pack(side="left",fill="x",expand=True,padx=(4,0))
        self.fix_box.bind("<<ComboboxSelected>>",lambda _:self._legacy_support_changed())
        self.load_box.bind("<<ComboboxSelected>>",lambda _:self._sync_faces())

        go=tk.Frame(right,bg=C["background"])
        go.pack(fill="x",pady=(0,12))
        self.run_button=ttk.Button(go,text="SOLVE",style="Accent.TButton",command=self.run)
        self.run_button.pack(side="left")
        tk.Label(go,textvariable=self.status,bg=C["background"],fg=C["muted"],
                 font=("Segoe UI",10),wraplength=490,justify="left",
                 anchor="w").pack(side="left",padx=16)

        results=self._panel(right,pady=13)
        row=tk.Frame(results,bg=C["panel"])
        row.pack(fill="x")
        ttk.Label(row,text="RESULTS",style="PanelTitle.TLabel").pack(side="left")
        self.result_state=tk.Label(row,text="NO ANALYSIS",bg=C["panel_high"],fg=C["muted"],
                                   font=("Segoe UI",9,"bold"),padx=11,pady=5)
        self.result_state.pack(side="right")
        summary=tk.Frame(results,bg=C["panel"])
        summary.pack(fill="x",pady=(16,13))
        for index,(caption,key) in enumerate((
            ("MAX MOVEMENT","max_displacement"),("PEAK STRESS","max_stress"),
        )):
            tile=tk.Frame(summary,bg=C["panel_high"],padx=14,pady=11)
            tile.grid(row=0,column=index,sticky="ew",padx=(0,8) if index==0 else (8,0))
            ttk.Label(tile,text=caption,style="Muted.TLabel").pack(anchor="w")
            tk.Label(tile,textvariable=self.result_vars[key],bg=C["panel_high"],
                     fg=C["accent"],font=("Segoe UI",19,"bold")).pack(anchor="w",pady=(4,0))
        summary.columnconfigure(0,weight=1,uniform="metrics")
        summary.columnconfigure(1,weight=1,uniform="metrics")
        self.balance_label=tk.Label(results,bg=C["panel"],fg=C["muted"],anchor="w",
                                    font=("Segoe UI",10),text="Force & moment checks will appear here.")
        self.balance_label.pack(fill="x")
        buttons=tk.Frame(results,bg=C["panel"])
        buttons.pack(fill="x",pady=(15,0))
        self.folder_button=ttk.Button(buttons,text="Open results",style="Quiet.TButton",
                                     command=self.show_folder,state="disabled")
        self.folder_button.pack(side="left")
        self.report_button=ttk.Button(buttons,text="Read report",style="Quiet.TButton",
                                     command=self.show_report,state="disabled")
        self.report_button.pack(side="left",padx=9)
        ttk.Label(results,text="Single solid · linear elastic · check fixtures, mesh and units before design use",
                  style="PanelMuted.TLabel").pack(anchor="w",pady=(13,0))

        self.activity_button=ttk.Button(right,text="Activity log  ▾",style="Quiet.TButton",
                                        command=self.toggle_activity)
        self.activity_button.pack(anchor="w")
        self.activity_frame=tk.Frame(right,bg=C["background"])
        self.logbox=tk.Text(self.activity_frame,height=5,wrap="word",state="disabled",
                            bg=C["panel"],fg=C["muted"],insertbackground=C["text"],
                            relief="flat",padx=12,pady=9,font=("Consolas",9))
        self.logbox.pack(fill="both",expand=True)

    def _input_signature(self):
        return (
            self.filename,self.source_sha256,
            tuple(self.support_faces),
            self.load_box.current(),
            self.force.get(),self.direction.get(),
            self.mesh.get(),self.e.get(),self.nu.get(),
            self.yield_mpa.get(),self.element_type.get(),
        )

    def _inputs_changed(self):
        if self.busy:
            self.status.set("Inputs changed while solving; results will need a new run.")
        elif self.latest is not None:
            self._clear_result()
            self.status.set("Setup changed. Press SOLVE to recalculate.")

    def _sync_faces(self):
        tags={f.tag for f in self.faces}
        self.support_faces=[tag for tag in self.support_faces if tag in tags]
        if self.support_faces:
            index=next(i for i,f in enumerate(self.faces) if f.tag==self.support_faces[0])
            self.fix_box.current(index)
        else:
            self.fixed.set("")
        loaded=self.load_box.current()
        self.picker.update_selection(
            supports=self.support_faces,
            suggested=self.suggested_support_faces,
            loaded=self.faces[loaded].tag if 0<=loaded<len(self.faces) else None)
        count=len(self.support_faces)
        self.picker.info.set(
            f"{count} HOLD face(s). Click HOLD and any highlighted face to remove. "
            f"{'Suggested fixture: review before solve.' if self.suggestions_review_pending else 'Click another face to add.'}"
            if count else "Click HOLD then a surface to add a support.")

    def _legacy_support_changed(self):
        index=self.fix_box.current()
        if 0<=index<len(self.faces):
            tag=self.faces[index].tag
            if tag not in self.support_faces:
                self.support_faces=[tag]
            self.suggested_support_faces.clear()
            self.suggestions_review_pending=False
        self._clear_result()
        self._sync_faces()

    def _on_fixture_hints(self,hints):
        # The preview was independently SHA-checked against the original STEP.
        # Never replace an operator-set support with inferred geometry.
        if not self.faces or self.support_faces or not self.filename:
            return
        try:
            sha=hashlib.sha256(Path(self.filename).read_bytes()).hexdigest()
            suggested=check_hints(
                hints,source_sha256=sha,face_ids=[f.tag for f in self.faces])
        except (OSError,ValueError) as exc:
            self._log("Attachment recognition declined: "+str(exc))
            return
        if suggested:
            self.support_faces=suggested
            self.suggested_support_faces=set(suggested)
            self.suggestions_review_pending=True
            self._sync_faces()
            self.status.set("Suggested mounting plane from round CAD features. Check HOLD, then choose LOAD.")
            self._log("Suggested ideal support at face(s) "+str(suggested)+
                      " from planar surfaces adjoining round features; real bolt/fixture NOT established.")

    def _on_face_click(self,role,tag):
        if self.busy:return False
        index=next((i for i,f in enumerate(self.faces) if f.tag==tag),None)
        if index is None:
            self.status.set("Clicked face is not in the current STEP part.")
            return False
        if role=="fixed":
            # Toggle: adding extra supports is as easy as removing one.
            if tag in self.support_faces:
                self.support_faces.remove(tag)
                self.suggested_support_faces.discard(tag)
            elif self.load_box.current()==index:
                self.status.set("Loaded face cannot also be held.")
                return False
            else:
                self.support_faces.append(tag)
                self.suggested_support_faces.discard(tag)
            # Any manually reviewed/edit operation removes inferred status
            # for that face. No later prompt is needed for manual additions.
            self.suggestions_review_pending=bool(self.suggested_support_faces)
            self._clear_result()
            self._sync_faces()
            self.status.set(f"{len(self.support_faces)} held surfaces selected. Choose LOAD or continue editing.")
            return True
        if tag in self.support_faces:
            self.status.set("Loaded face cannot also be held. Remove HOLD first.")
            return False
        self.load_box.current(index)
        self._clear_result()
        self._sync_faces()
        self.status.set("LOAD face selected. Review supports and press SOLVE.")
        return True

    def toggle_advanced(self):
        self.advanced_open=not self.advanced_open
        self.advanced_button.configure(text="More settings  ▴" if self.advanced_open else "More settings  ▾")
        if self.advanced_open:self.advanced_frame.pack(fill="x",pady=(9,0))
        else:self.advanced_frame.pack_forget()

    def toggle_activity(self):
        self.activity_open=not self.activity_open
        self.activity_button.configure(text="Activity log  ▴" if self.activity_open else "Activity log  ▾")
        if self.activity_open:self.activity_frame.pack(fill="both",expand=True,pady=(7,0))
        else:self.activity_frame.pack_forget()

    def _log(self,line):
        self.logbox.configure(state="normal")
        self.logbox.insert("end",str(line)+"\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _clear_result(self):
        self.latest=None
        self.folder_button.configure(state="disabled")
        self.report_button.configure(state="disabled")
        self.result_state.configure(text="NO ANALYSIS",fg=C["muted"])
        self.balance_label.configure(text="Force & moment checks will appear here.",fg=C["muted"])
        for var in self.result_vars.values():var.set("—")

    def _set_busy(self,value):
        self.busy=value
        state="disabled" if value else "normal"
        for btn in (self.run_button,self.open_button,self.demo_button):
            btn.configure(state=state)
        for combo in (self.fix_box,self.load_box):
            combo.configure(state="disabled" if value else "readonly")

    def demo(self):
        if self.busy:return
        try:
            from ezfea.demo import make_demo_step
            source=make_demo_step()
            if self.load_file(str(source)):
                left=min(range(len(self.faces)),key=lambda i:abs(self.faces[i].center_mm[0]))
                right=max(range(len(self.faces)),key=lambda i:self.faces[i].center_mm[0])
                self.fix_box.current(left)
                self.support_faces=[self.faces[left].tag]
                self.load_box.current(right)
                self._sync_faces()
                self.status.set("Example ready. Press SOLVE.")
                self._log("Example: real 100 × 10 × 10 mm STEP, left fixed, 100 N down.")
        except Exception as exc:
            messagebox.showerror("Example could not open",str(exc))

    def open_file(self):
        if self.busy:return
        selected=filedialog.askopenfilename(filetypes=[("STEP geometry","*.step *.stp")])
        if selected:self.load_file(selected)

    def load_file(self,selected):
        if self.busy:return False
        try:
            faces=inspect_step(selected,require_single_solid=True)
            if len(faces)<2:
                raise ValueError("No usable closed-solid CAD faces were found.")
            source_sha=hashlib.sha256(Path(selected).read_bytes()).hexdigest()
        except Exception as exc:
            self._log("IMPORT ERROR: "+str(exc))
            messagebox.showerror("Cannot import STEP",str(exc))
            return False
        self._clear_result()
        self.filename=str(Path(selected).resolve())
        self.source_sha256=source_sha
        self.faces=faces
        self.support_faces=[]
        self.suggested_support_faces=set()
        self.suggestions_review_pending=False
        self.fixed.set("")
        self.loaded.set("")
        self.fix_box["values"]=[f.label for f in faces]
        self.load_box["values"]=[f.label for f in faces]
        self.part_name.set(Path(selected).name)
        self.part_detail.set(f"{len(faces)} CAD faces loaded  •  STEP  •  mm geometry")
        self.picker.start_preview(self.filename,[f.tag for f in faces])
        self.status.set("Select held face and loaded face.")
        self._log(f"Imported {len(faces)} real CAD faces from {self.filename}.")
        return True

    def run(self):
        if self.busy:return
        try:
            values={
                "fx":"0","fy":"0","fz":"0",
                "mesh":self.mesh.get(),"e":self.e.get(),"nu":self.nu.get(),
                "yield_mpa":self.yield_mpa.get(),"element_type":self.element_type.get(),
            }
            fx,fy,fz=force_components(self.force.get(),self.direction.get())
            self.fx.set(str(fx))
            self.fy.set(str(fy))
            self.fz.set(str(fz))
            values.update(fx=fx,fy=fy,fz=fz)
            if (not self.source_sha256 or
                hashlib.sha256(Path(self.filename).read_bytes()).hexdigest()!=self.source_sha256):
                raise ValueError(
                    "The STEP file changed since import. Reopen the file to "
                    "refresh face IDs before solving."
                )
            case=build_multi_analysis(
                self.filename,self.faces,
                [{"face":t,"axes":[1,2,3]} for t in self.support_faces],
                self.load_box.current(),values)
            missing=preflight()
            if missing:raise ValueError("\n".join(missing))
        except (OSError,ValueError,TypeError) as exc:
            self.status.set("Check your setup.")
            messagebox.showerror("Cannot solve",str(exc))
            return
        if self.suggestions_review_pending:
            confirmed=messagebox.askyesno(
                "Confirm suggested mounting surface",
                "EZ-FEA recognized planar surface(s) next to round CAD features. "
                "It cannot know whether these are bolt holes or how the joint is restrained.\n\n"
                "Treat the highlighted HOLD surfaces as fully fixed for this analysis? "
                "Click No to edit or remove the suggestion.")
            if not confirmed:
                self.status.set("Review suggested supports: click HOLD to remove or change.")
                return
            self.suggestions_review_pending=False
            self.suggested_support_faces.clear()
            self._sync_faces()
        self._clear_result()
        self.active_run_signature=self._input_signature()
        self._set_busy(True)
        self.status.set("Meshing and solving…")
        self.result_state.configure(text="SOLVING",fg=C["accent"])
        self._log(f"Real Gmsh + CalculiX: {case.element_type}, {case.mesh_size_mm:g} mm.")
        threading.Thread(target=self._solve,args=(case,),daemon=True).start()

    def _solve(self,case):
        try:self.responses.put(("ok",run_native_child_process(case)))
        except Exception as exc:self.responses.put(("failed",str(exc)))

    def _poll(self):
        try:
            while True:
                kind,value=self.responses.get_nowait()
                self._set_busy(False)
                if kind=="ok":
                    if (self.active_run_signature!=self._input_signature()
                        or value["record"].get("input_sha256")!=self.source_sha256):
                        self._clear_result()
                        self.status.set("Settings or source changed during solve. Rerun to see current results.")
                        self._log("OUTDATED: solver completed for earlier settings at "+str(value["folder"]))
                        continue
                    self.latest=value
                    for key,var in self.result_vars.items():
                        var.set(value["summary"].get(key,"—"))
                    self.folder_button.configure(state="normal")
                    self.report_button.configure(state="normal")
                    briefing=brief_native_result(value["summary"])
                    ok=briefing["state"]=="SOLVED"
                    self.result_state.configure(text=briefing["state"],
                                                fg=C["accent"] if ok else C["danger"])
                    self.balance_label.configure(text=briefing["balance"],
                                                 fg=C["accent"] if ok else C["danger"])
                    self.status.set("Analysis complete." if ok else "Results need review.")
                    self._log(("SOLVED: " if ok else "REVIEW: ")+str(value["folder"]))
                else:
                    self.status.set("Solver error — see activity log.")
                    self.result_state.configure(text="ERROR",fg=C["danger"])
                    self._log("SOLVER ERROR: "+str(value))
                    if not self.activity_open:self.toggle_activity()
                    messagebox.showerror("Analysis could not finish",str(value))
        except queue.Empty:
            pass
        finally:
            self.after(150,self._poll)

    def show_folder(self):
        if not self.latest:return
        try:open_result_folder(self.latest["folder"])
        except Exception as exc:messagebox.showerror("Cannot open results",str(exc))

    def show_report(self):
        if not self.latest:return
        try:report=self.latest["report"].read_text(encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Cannot read report",str(exc))
            return
        win=tk.Toplevel(self)
        win.configure(bg=C["background"])
        win.title("EZ-FEA | Results")
        win.geometry("750x560")
        frame=tk.Frame(win,bg=C["background"],padx=15,pady=15)
        frame.pack(fill="both",expand=True)
        view=tk.Text(frame,wrap="word",bg=C["panel"],fg=C["text"],
                     font=("Consolas",10),relief="flat",padx=15,pady=15)
        bar=ttk.Scrollbar(frame,orient="vertical",command=view.yview)
        view.configure(yscrollcommand=bar.set)
        bar.pack(side="right",fill="y")
        view.pack(side="left",fill="both",expand=True)
        view.insert("1.0",report)
        view.configure(state="disabled")


if __name__=="__main__":
    App().mainloop()
