"""EZ-FEA: simple desktop STEP-to-CalculiX interface."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from ezfea.core import Analysis, Material
from ezfea.mesh import inspect_step
from ezfea.workflow import run_case

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EZ-FEA | Structural Analysis")
        self.geometry("780x600")
        self.minsize(640,550)
        self.responses=queue.Queue()
        self.filename=""
        self.faces=[]
        self.fixed=tk.StringVar()
        self.loaded=tk.StringVar()
        self.mesh=tk.StringVar(value="5")
        self.fx=tk.StringVar(value="0")
        self.fy=tk.StringVar(value="-100")
        self.fz=tk.StringVar(value="0")
        self.e=tk.StringVar(value="200000")
        self.nu=tk.StringVar(value="0.26")
        self.yield_mpa=tk.StringVar(value="250")
        self.build()
        self.after(200,self.poll)

    def build(self):
        root=ttk.Frame(self,padding=18)
        root.pack(fill="both",expand=True)
        ttk.Label(root,text="EZ-FEA",font=("Segoe UI",22,"bold")).pack(anchor="w")
        ttk.Label(root,text="Open STEP  |  Connections  |  Force  |  Run").pack(anchor="w")
        ttk.Label(root,text="EXPERIMENTAL: not validated for engineering sign-off",
                  foreground="#a33").pack(anchor="w",pady=9)
        row=ttk.Frame(root); row.pack(fill="x",pady=6)
        ttk.Button(row,text="Open STEP part",command=self.open_file).pack(side="left")
        ttk.Button(row,text="Demo beam",command=self.demo).pack(side="left",padx=8)
        self.path_label=ttk.Label(row,text="No file selected")
        self.path_label.pack(side="left",padx=12)
        region=ttk.LabelFrame(root,text="Connections and Load",padding=10)
        region.pack(fill="x",pady=10)
        ttk.Label(region,text="Connection: fully fixed CAD face").pack(anchor="w")
        self.fix_box=ttk.Combobox(region,textvariable=self.fixed,state="readonly",width=75)
        self.fix_box.pack(fill="x",pady=5)
        ttk.Label(region,text="Total force: applied to CAD face").pack(anchor="w")
        self.load_box=ttk.Combobox(region,textvariable=self.loaded,state="readonly",width=75)
        self.load_box.pack(fill="x",pady=5)
        panel=ttk.LabelFrame(root,text="Units: mm, N, MPa",padding=10)
        panel.pack(fill="x")
        for i,(label,var) in enumerate([
            ("Fx (N)",self.fx),("Fy (N)",self.fy),("Fz (N)",self.fz),
            ("Mesh (mm)",self.mesh),("E (MPa)",self.e),("Poisson",self.nu),
            ("Yield (MPa)",self.yield_mpa)
        ]):
            sub=ttk.Frame(panel); sub.grid(row=i//4,column=i%4,sticky="ew",padx=6,pady=3)
            ttk.Label(sub,text=label).pack(anchor="w")
            ttk.Entry(sub,textvariable=var,width=12).pack(fill="x")
        for i in range(4):panel.columnconfigure(i,weight=1)
        self.run_button=ttk.Button(root,text="RUN ANALYSIS",command=self.run)
        self.run_button.pack(anchor="w",pady=14)
        ttk.Label(root,text="Solver diagnostics",font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.logbox=tk.Text(root,height=9,wrap="word",state="disabled")
        self.logbox.pack(fill="both",expand=True)
        self.log("Choose a closed STEP solid. Face centers are listed in mm.")

    def log(self,line):
        self.logbox.configure(state="normal")
        self.logbox.insert("end",str(line)+"\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def demo(self):
        try:
            from ezfea.demo import make_demo_step
            self.load_file(str(make_demo_step()))
            left=min(range(len(self.faces)),key=lambda i:abs(self.faces[i].center_mm[0]))
            right=min(range(len(self.faces)),key=lambda i:abs(self.faces[i].center_mm[0]-100))
            self.fix_box.current(left)
            self.load_box.current(right)
            self.log("Demo: 100 x 10 x 10 mm cantilever; fixed left end, 100 N downward at right end.")
        except Exception as exc:
            messagebox.showerror("Demo creation failed",str(exc))

    def open_file(self):
        selected=filedialog.askopenfilename(filetypes=[("STEP models","*.step *.stp")])
        if selected:self.load_file(selected)

    def load_file(self,selected):
        try:
            faces=inspect_step(selected)
        except Exception as exc:
            messagebox.showerror("Import failed",str(exc))
            self.log(str(exc))
            return
        self.filename=selected
        self.faces=faces
        self.path_label.configure(text=Path(selected).name)
        names=[f.label for f in faces]
        self.fix_box["values"]=names;self.load_box["values"]=names
        if names:self.fix_box.current(0)
        if len(names)>1:self.load_box.current(-1+len(names))
        self.log(f"Imported {len(faces)} faces. Select a fixed face and a load face.")

    def run(self):
        try:
            i,j=self.fix_box.current(),self.load_box.current()
            if i<0 or j<0 or not self.faces:
                raise ValueError("Import a STEP solid and choose connection and load faces.")
            case=Analysis(self.filename,self.faces[i].tag,self.faces[j].tag,
                          (float(self.fx.get()),float(self.fy.get()),float(self.fz.get())),
                          float(self.mesh.get()),
                          Material(elastic_modulus_mpa=float(self.e.get()),
                                   poisson_ratio=float(self.nu.get()),
                                   yield_mpa=float(self.yield_mpa.get())))
            case.validate()
        except ValueError as exc:
            messagebox.showerror("Check inputs",str(exc));return
        self.run_button.configure(state="disabled")
        self.log("Meshing and solving with free Gmsh and CalculiX...")
        threading.Thread(target=self.solve,args=(case,),daemon=True).start()

    def solve(self,case):
        try:self.responses.put(("ok",run_case(case)))
        except Exception as exc:self.responses.put(("failed",str(exc)))

    def poll(self):
        try:
            while True:
                state,value=self.responses.get_nowait()
                self.run_button.configure(state="normal")
                if state=="ok":
                    self.log(f"Completed. Files in {value}")
                    self.log("Use free CalculiX GraphiX to view analysis.frd stress/displacement.")
                    messagebox.showinfo("Completed",f"Result directory:\n{value}")
                else:
                    self.log("FAILED: "+str(value))
                    messagebox.showerror("Analysis failed",str(value))
        except queue.Empty:pass
        finally:self.after(200,self.poll)

if __name__=="__main__":
    App().mainloop()
