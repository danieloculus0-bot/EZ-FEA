"""Minimal one-window STEP surface picker with original CAD face IDs.

No new graphics dependencies: Gmsh triangulates the source STEP in a
separate Python process and a Tk Canvas draws the true CAD surface patches.
Hold/Load clicks return the exact OCC surface ID consumed by the solver.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk

from .desktop_presentation import PALETTE as COLOR
from .desktop_preview import validate_preview, projected_triangles, face_under_cursor


class FacePicker(tk.Frame):
    def __init__(self,parent,on_face):
        super().__init__(parent,bg=COLOR["panel"],
                         highlightbackground=COLOR["border"],highlightthickness=1)
        self.on_face=on_face
        self.source=None
        self.epoch=0
        self.mode="fixed"
        self.fixed_tag=None
        self.loaded_tag=None
        self.triangles=[]
        self.painted=[]
        self.yaw=-.55
        self.pitch=.40
        self.zoom=1.
        self.drag_origin=None
        self.dragged=False
        head=tk.Frame(self,bg=COLOR["panel"],padx=12,pady=8)
        head.pack(fill="x")
        tk.Label(head,text="YOUR PART",bg=COLOR["panel"],fg=COLOR["text"],
                 font=("Segoe UI",11,"bold")).pack(side="left")
        tk.Label(head,text="Drag to rotate  ·  Scroll to zoom",bg=COLOR["panel"],
                 fg=COLOR["muted"],font=("Segoe UI",9)).pack(side="right")
        self.canvas=tk.Canvas(self,bg="#111a18",height=260,
                              highlightthickness=0,cursor="crosshair")
        self.canvas.pack(fill="both",expand=True,padx=6)
        self.canvas.bind("<Configure>",lambda _e:self.draw())
        self.canvas.bind("<ButtonPress-1>",self._down)
        self.canvas.bind("<B1-Motion>",self._drag)
        self.canvas.bind("<ButtonRelease-1>",self._up)
        self.canvas.bind("<MouseWheel>",self._wheel)
        self.canvas.bind("<Button-4>",lambda _:self._zoom(1.12))
        self.canvas.bind("<Button-5>",lambda _:self._zoom(1/1.12))
        self.canvas.bind("<Double-Button-1>",lambda _:self.reset_camera())
        buttons=tk.Frame(self,bg=COLOR["panel"],padx=10,pady=8)
        buttons.pack(fill="x")
        buttons.grid_columnconfigure(0,weight=1)
        buttons.grid_columnconfigure(1,weight=1)
        self.hold_button=tk.Button(
            buttons,text="HOLD · click face",command=lambda:self.choose("fixed"),
            font=("Segoe UI",10,"bold"),relief="flat",borderwidth=0,pady=12,
            cursor="hand2")
        self.load_button=tk.Button(
            buttons,text="LOAD · click face",command=lambda:self.choose("loaded"),
            font=("Segoe UI",10,"bold"),relief="flat",borderwidth=0,pady=12,
            cursor="hand2")
        self.hold_button.grid(row=0,column=0,sticky="ew",padx=(0,5))
        self.load_button.grid(row=0,column=1,sticky="ew",padx=(5,0))
        self.info=tk.StringVar(value="Open STEP or use the example")
        tk.Label(self,textvariable=self.info,bg=COLOR["panel"],fg=COLOR["muted"],
                 font=("Segoe UI",9),anchor="w",justify="left",
                 wraplength=680,padx=12,pady=8).pack(fill="x")
        self._update_buttons()

    def _update_buttons(self):
        for name,button,tag in (
            ("fixed",self.hold_button,self.fixed_tag),
            ("loaded",self.load_button,self.loaded_tag),
        ):
            active=self.mode==name
            accent="#5ff39a" if name=="fixed" else "#ffc27b"
            button.configure(
                text=("HOLD" if name=="fixed" else "LOAD")+
                     (" · face "+str(tag) if tag is not None else " · click face"),
                bg=accent if active else COLOR["panel_high"],
                fg=COLOR["background"] if active else COLOR["text"],
                activebackground=accent,activeforeground=COLOR["background"])

    def choose(self,mode):
        if mode not in ("fixed","loaded"):
            raise ValueError("Unknown face selection mode")
        self.mode=mode
        self._update_buttons()
        if self.triangles:
            self.info.set("Click a face to "+("hold" if mode=="fixed" else "load")+
                          " · Drag to rotate")
        else:
            self.info.set("Preview loading · face ID fallback under More settings")

    def update_selection(self,*,fixed=None,loaded=None):
        self.fixed_tag=fixed
        self.loaded_tag=loaded
        self._update_buttons()
        self.draw()

    def start_preview(self,source,face_ids):
        path=Path(source).resolve()
        self.epoch+=1
        epoch=self.epoch
        self.source=str(path)
        self.triangles=[]
        self.painted=[]
        self.fixed_tag=self.loaded_tag=None
        self.choose("fixed")
        self.info.set("Reading actual STEP surface faces…")
        self.draw()
        expected_sha=hashlib.sha256(path.read_bytes()).hexdigest()
        threading.Thread(
            target=self._worker,
            args=(epoch,str(path),expected_sha,tuple(face_ids)),
            daemon=True,
        ).start()

    def _worker(self,epoch,source,sha,faces):
        try:
            with tempfile.TemporaryDirectory(prefix="ezfea-cad-preview-") as temp:
                output=Path(temp)/"cad.json"
                completed=subprocess.run(
                    [sys.executable,"-m","ezfea.desktop_preview",source,str(output)],
                    cwd=str(Path(__file__).resolve().parent.parent),
                    text=True,capture_output=True,timeout=140)
                if completed.returncode!=0:
                    raise ValueError((completed.stderr or completed.stdout or
                                      "Surface mesh generation failed").strip()[-650:])
                parsed=json.loads(output.read_text(encoding="utf-8"))
            tris=validate_preview(parsed,expected_sha=sha,expected_faces=faces)
            self.after(0,lambda:self._finish(epoch,tris,None))
        except Exception as exc:
            message=str(exc)
            self.after(0,lambda:self._finish(epoch,None,message))

    def _finish(self,epoch,triangles,error):
        if epoch!=self.epoch:return
        if error:
            self.triangles=[]
            self.info.set("3D preview unavailable · use CAD face IDs under More settings")
        else:
            self.triangles=triangles
            self.info.set("Click the face to HOLD · drag to rotate · scroll to zoom")
        self.draw()

    def draw(self):
        if not hasattr(self,"canvas"):return
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        self.canvas.delete("all")
        if w<30 or h<30:return
        if not self.triangles:
            self.painted=[]
            self.canvas.create_text(w/2,h/2,
                 text="3D STEP PREVIEW",fill=COLOR["muted"],
                 font=("Segoe UI",12,"bold"))
            return
        self.painted=projected_triangles(
            self.triangles,w,h,self.yaw,self.pitch,self.zoom)
        neutrals=("#34483e","#3c5148","#43594e","#4c6155","#51665b")
        for _depth,tag,vertices in self.painted:
            shade=("#5ff39a" if tag==self.fixed_tag else
                   "#ffc27b" if tag==self.loaded_tag else neutrals[tag%len(neutrals)])
            coordinates=[v for pair in vertices for v in pair]
            self.canvas.create_polygon(*coordinates,
                fill=shade,outline="#192923",width=.4,
                tags=("cad_surface",f"face_{tag}"))

    def _down(self,event):
        self.drag_origin=(event.x,event.y,self.yaw,self.pitch)
        self.dragged=False

    def _drag(self,event):
        if self.drag_origin is None:return
        x,y,yaw,pitch=self.drag_origin
        dx,dy=event.x-x,event.y-y
        if abs(dx)+abs(dy)>5:self.dragged=True
        if not self.dragged:return
        self.yaw=yaw+dx*.01
        self.pitch=max(-1.42,min(1.42,pitch+dy*.01))
        self.draw()

    def _up(self,event):
        if self.drag_origin is None:return
        x,y,_,_=self.drag_origin
        self.drag_origin=None
        if self.dragged or abs(event.x-x)+abs(event.y-y)>5:return
        face=face_under_cursor(self.painted,event.x,event.y)
        if face is not None:
            # Parent verifies mapping back to the original inspect_step list.
            if self.on_face(self.mode,face) is not False:
                if self.mode=="fixed":self.choose("loaded")

    def _wheel(self,event):
        self._zoom(1.12 if event.delta>0 else 1/1.12)

    def _zoom(self,factor):
        self.zoom=max(.35,min(3.,self.zoom*factor))
        self.draw()

    def reset_camera(self):
        self.yaw,self.pitch,self.zoom=-.55,.40,1.
        self.draw()
