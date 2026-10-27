"""EZ-FEA desktop: pick a STEP, support it, load it, and see REAL 3D results.

Launch from the repository root: python app.py
Local desktop program; native Gmsh and CalculiX are required to solve.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ezfea.mesh import inspect_step
from ezfea.desktop_controller import (
    build_analysis, open_result_folder, preflight, run_desktop_case,
)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EZ-FEA | Structural Analysis")
        self.geometry("870x770")
        self.minsize(720,660)
        self.responses=queue.Queue()
        self.filename=""
        self.faces=[]
        self.busy=False
        self.latest=None
        self.fixed=tk.StringVar()
        self.loaded=tk.StringVar()
        self.mesh=tk.StringVar(value="7")
        self.fx=tk.StringVar(value="0")
        self.fy=tk.StringVar(value="-100")
        self.fz=tk.StringVar(value="0")
        self.e=tk.StringVar(value="200000")
        self.nu=tk.StringVar(value="0.26")
        self.yield_mpa=tk.StringVar(value="250")
        self.element_type=tk.StringVar(value="C3D10")
        self.status=tk.StringVar(value="Choose a STEP part or open the demo.")
        self.result_vars={
            key:tk.StringVar(value="—")
            for key in ("headline","max_displacement","max_stress",
                        "yield_ratio","force_balance","moment_balance",
                        "elements","element_type")
        }
        self._build()
        self.after(150,self._poll)
        missing=preflight()
        if missing:
            self._log("Native solver setup required:")
            for issue in missing:self._log("• "+issue)
        else:self._log("Gmsh and CalculiX found. Native solving available.")
        self._log("Supports: one continuous STEP solid and a fully fixed face.")

    def _build(self):
        style=ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel",font=("Segoe UI",21,"bold"))
        style.configure("Heading.TLabel",font=("Segoe UI",11,"bold"))
        style.configure("Big.TButton",font=("Segoe UI",11,"bold"),padding=(14,11))
        style.configure("Status.TLabel",font=("Segoe UI",10,"bold"))
        root=ttk.Frame(self,padding=16)
        root.pack(fill="both",expand=True)
        ttk.Label(root,text="EZ-FEA",style="Title.TLabel").pack(anchor="w")
        ttk.Label(root,text="1. Open part     2. Select support and load     3. Solve     4. Read results").pack(anchor="w",pady=(0,8))
        ttk.Label(root,text="Single-part, linear-static 3D analysis · N / mm / MPa · Not validated for design sign-off",
                  foreground="#9f472a").pack(anchor="w",pady=(0,10))

        file_row=ttk.Frame(root)
        file_row.pack(fill="x",pady=(0,9))
        self.open_button=ttk.Button(file_row,text="Open STEP",command=self.open_file)
        self.open_button.pack(side="left")
        self.demo_button=ttk.Button(file_row,text="Try demo",command=self.demo)
        self.demo_button.pack(side="left",padx=9)
        self.path_label=ttk.Label(file_row,text="No part loaded")
        self.path_label.pack(side="left",padx=9)

        region=ttk.LabelFrame(root,text="1 · CAD faces",padding=10)
        region.pack(fill="x",pady=5)
        ttk.Label(region,text="Fixed face (all three translations restrained)").pack(anchor="w")
        self.fix_box=ttk.Combobox(region,textvariable=self.fixed,state="readonly")
        self.fix_box.pack(fill="x",pady=(2,6))
        ttk.Label(region,text="Loaded face (total force spread over the face)").pack(anchor="w")
        self.load_box=ttk.Combobox(region,textvariable=self.loaded,state="readonly")
        self.load_box.pack(fill="x",pady=(2,1))
        ttk.Label(region,text="CAD face IDs are taken from the imported STEP, not the browser preview.",
                  foreground="#606060").pack(anchor="w")

        settings=ttk.LabelFrame(root,text="2 · Force, material and mesh",padding=10)
        settings.pack(fill="x",pady=7)
        fields=[
            ("Fx (N)",self.fx),("Fy (N)",self.fy),("Fz (N)",self.fz),
            ("Mesh size (mm)",self.mesh),("Young's E (MPa)",self.e),
            ("Poisson's ratio",self.nu),("Nominal yield (MPa)",self.yield_mpa)
        ]
        for i,(name,var) in enumerate(fields):
            cell=ttk.Frame(settings)
            cell.grid(row=i//4,column=i%4,sticky="ew",padx=4,pady=5)
            ttk.Label(cell,text=name).pack(anchor="w")
            ttk.Entry(cell,textvariable=var,width=14).pack(fill="x",pady=(2,0))
        ecell=ttk.Frame(settings)
        ecell.grid(row=1,column=3,sticky="ew",padx=4,pady=5)
        ttk.Label(ecell,text="3D elements").pack(anchor="w")
        ttk.Combobox(ecell,textvariable=self.element_type,
                     values=("C3D10","C3D4"),state="readonly",width=13).pack(fill="x",pady=(2,0))
        for i in range(4):settings.grid_columnconfigure(i,weight=1)

        go=ttk.Frame(root)
        go.pack(fill="x",pady=9)
        self.run_button=ttk.Button(go,text="RUN REAL 3D ANALYSIS",style="Big.TButton",command=self.run)
        self.run_button.pack(side="left")
        ttk.Label(go,textvariable=self.status,style="Status.TLabel",
                  wraplength=450).pack(side="left",padx=12)

        result_frame=ttk.LabelFrame(root,text="3 · Actual solver results",padding=11)
        result_frame.pack(fill="x",pady=5)
        ttk.Label(result_frame,textvariable=self.result_vars["headline"],
                  style="Heading.TLabel").pack(anchor="w",pady=(0,6))
        table=ttk.Frame(result_frame)
        table.pack(fill="x")
        labels=[
            ("Maximum movement","max_displacement"),
            ("Peak von Mises stress","max_stress"),
            ("Nominal yield/stress ratio*","yield_ratio"),
            ("Force equilibrium","force_balance"),
            ("Moment equilibrium","moment_balance"),
            ("Mesh elements","elements"),
        ]
        for i,(label,key) in enumerate(labels):
            ttk.Label(table,text=label).grid(row=i,column=0,sticky="w",pady=2)
            ttk.Label(table,textvariable=self.result_vars[key],
                      style="Heading.TLabel").grid(row=i,column=1,sticky="w",padx=16,pady=2)
        ttk.Label(result_frame,text="*Ratio is not a safety certification. Peak stress may require mesh convergence.",
                  foreground="#7c5525").pack(anchor="w",pady=(7,1))
        buttons=ttk.Frame(result_frame)
        buttons.pack(fill="x",pady=(7,0))
        self.folder_button=ttk.Button(buttons,text="Open result folder",
                                      command=self.show_folder,state="disabled")
        self.folder_button.pack(side="left")
        self.report_button=ttk.Button(buttons,text="View report",command=self.show_report,
                                      state="disabled")
        self.report_button.pack(side="left",padx=8)

        ttk.Label(root,text="Activity",style="Heading.TLabel").pack(anchor="w",pady=(7,3))
        self.logbox=tk.Text(root,height=5,wrap="word",state="disabled")
        self.logbox.pack(fill="both",expand=True)

    def _log(self,line):
        self.logbox.configure(state="normal")
        self.logbox.insert("end",str(line)+"\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _clear_result(self):
        self.latest=None
        self.folder_button.configure(state="disabled")
        self.report_button.configure(state="disabled")
        for var in self.result_vars.values():var.set("—")

    def _set_busy(self,value):
        self.busy=value
        state="disabled" if value else "normal"
        for button in (self.run_button,self.open_button,self.demo_button):
            button.configure(state=state)
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
                self.load_box.current(right)
                self.status.set("Demo selected. Press RUN REAL 3D ANALYSIS.")
                self._log("Demo 100 × 10 × 10 mm STEP: fully fixed left, 100 N downward at right.")
        except Exception as exc:
            messagebox.showerror("Demo could not open",str(exc))

    def open_file(self):
        if self.busy:return
        selected=filedialog.askopenfilename(filetypes=[("STEP geometry","*.step *.stp")])
        if selected:self.load_file(selected)

    def load_file(self,selected):
        if self.busy:return False
        try:
            faces=inspect_step(selected)
            if len(faces)<2:
                raise ValueError("No usable closed-solid CAD faces were found.")
        except Exception as exc:
            self._log("IMPORT ERROR: "+str(exc))
            messagebox.showerror("Cannot import STEP",str(exc))
            return False
        self._clear_result()
        self.filename=str(Path(selected).resolve())
        self.faces=faces
        self.fixed.set("")
        self.loaded.set("")
        self.fix_box["values"]=[f.label for f in faces]
        self.load_box["values"]=[f.label for f in faces]
        self.path_label.configure(text=Path(selected).name)
        self.status.set("Choose the fixed face and loaded face.")
        self._log(f"Imported {len(faces)} CAD faces from {self.filename}.")
        return True

    def run(self):
        if self.busy:return
        try:
            values={
                "fx":self.fx.get(),"fy":self.fy.get(),"fz":self.fz.get(),
                "mesh":self.mesh.get(),"e":self.e.get(),"nu":self.nu.get(),
                "yield_mpa":self.yield_mpa.get(),
                "element_type":self.element_type.get(),
            }
            case=build_analysis(self.filename,self.faces,
                                self.fix_box.current(),self.load_box.current(),values)
            missing=preflight()
            if missing:raise ValueError("\n".join(missing))
        except (ValueError,TypeError) as exc:
            self.status.set("Check setup inputs.")
            messagebox.showerror("Cannot start analysis",str(exc))
            return
        self._clear_result()
        self._set_busy(True)
        self.status.set("Meshing and solving the real STEP geometry…")
        self._log(f"Starting Gmsh + CalculiX: {case.element_type}, {case.mesh_size_mm:g} mm mesh.")
        threading.Thread(target=self._solve,args=(case,),daemon=True).start()

    def _solve(self,case):
        try:
            self.responses.put(("ok",run_desktop_case(case)))
        except Exception as exc:
            self.responses.put(("failed",str(exc)))

    def _poll(self):
        try:
            while True:
                kind,value=self.responses.get_nowait()
                self._set_busy(False)
                if kind=="ok":
                    self.latest=value
                    for key,var in self.result_vars.items():
                        var.set(value["summary"].get(key,"—"))
                    self.folder_button.configure(state="normal")
                    self.report_button.configure(state="normal")
                    status=value["summary"]["status"]
                    if status=="completed":
                        self.status.set("Finished · force and moment checks passed.")
                        self._log("SOLVED: "+str(value["folder"]))
                    else:
                        self.status.set("Finished, but equilibrium checks need review.")
                        self._log("NEEDS REVIEW: "+str(value["folder"]))
                    self._log("Actual stress and movement are shown above; RESULTS.txt saved.")
                else:
                    self.status.set("Solver failed. Read the message below.")
                    self._log("SOLVER ERROR: "+str(value))
                    messagebox.showerror("Native analysis failed",str(value))
        except queue.Empty:
            pass
        finally:
            self.after(150,self._poll)

    def show_folder(self):
        if not self.latest:return
        try:open_result_folder(self.latest["folder"])
        except Exception as exc:messagebox.showerror("Cannot open folder",str(exc))

    def show_report(self):
        if not self.latest:return
        path=self.latest["report"]
        try:text=path.read_text(encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Cannot read report",str(exc));return
        window=tk.Toplevel(self)
        window.title("EZ-FEA | Native result report")
        window.geometry("780x580")
        frame=ttk.Frame(window,padding=10)
        frame.pack(fill="both",expand=True)
        view=tk.Text(frame,wrap="word")
        scrollbar=ttk.Scrollbar(frame,orient="vertical",command=view.yview)
        view.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right",fill="y")
        view.pack(side="left",fill="both",expand=True)
        view.insert("1.0",text)
        view.configure(state="disabled")


if __name__=="__main__":
    App().mainloop()
