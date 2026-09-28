"""
Controles de teclado:
  W/A/S/D o flechas -> mover (mientras la tecla está presionada)
  Espacio           -> disparar

"""

import math
import time
import tkinter as tk

# ----------------------------------------------------------------------
# Estilo
# ----------------------------------------------------------------------
FUENTE = "Segoe UI"
BG = "#EEF2F1"
PANEL = "#FFFFFF"
BORDE = "#D5DDDB"
INK = "#1F2D33"
MUTED = "#66777F"
TEAL = "#1B9AA0"
TEAL_OSCURO = "#12777C"
AMARILLO = "#FFC629"
AMARILLO_OSCURO = "#E3AA0E"
ROSA = "#D63384"
ALERTA = "#E8590C"

# ----------------------------------------------------------------------
# Parámetros
# ----------------------------------------------------------------------
ESC = 1.6              # píxeles por cm en la vista de simulación
ENFRIAMIENTO_S = 0.8   # tiempo mínimo entre disparos
HISTERESIS_CM = 15     # margen extra para dejar de girar al esquivar
RANGO_SENSOR_CM = 200  # el sensor de distancia no mide más allá de esto


# ======================================================================
# Robots
# ======================================================================
class Robot:
    """Interfaz común. La ventana solo usa estos métodos."""

    es_simulacion = False

    def mover(self, direccion):
        """direccion: 'adelante', 'atras', 'izquierda', 'derecha' o 'detener'."""
        raise NotImplementedError

    def disparar(self, potencia):
        """potencia: número de 0 a 100 (%)."""
        raise NotImplementedError

    def distancia_cm(self):
        """Distancia medida por el sensor en cm, o None si no detecta nada."""
        raise NotImplementedError

    def actualizar(self, dt):
        """Avanza la simulación dt segundos. En el robot real no hace nada."""


class RobotSimulado(Robot):
    """Robot virtual en una arena de 200 x 200 cm, vista desde arriba."""

    es_simulacion = True
    ARENA = 200.0
    RADIO = 9.0            # cm
    V_LINEAL = 35.0        # cm/s
    V_GIRO = 100.0         # grados/s
    ALCANCE_MAX = 160.0    # cm con potencia 100 %
    V_BOLA = 260.0         # cm/s

    def __init__(self):
        self.x, self.y = 100.0, 178.0
        self.rumbo = -90.0  # grados: 0 = derecha, -90 = arriba (eje y hacia abajo)
        self.orden = "detener"
        self.obstaculos = [(30, 50, 80, 80), (125, 90, 170, 120), (85, 125, 110, 150)]
        self.bolas = []
        self.impactos = []  # (x, y, instante en que desaparece)
        self.t = 0.0

    # -- geometría -----------------------------------------------------
    def _fuera(self, x, y):
        return not (0 <= x <= self.ARENA and 0 <= y <= self.ARENA)

    def _en_obstaculo(self, x, y, margen=0.0):
        for x1, y1, x2, y2 in self.obstaculos:
            if x1 - margen < x < x2 + margen and y1 - margen < y < y2 + margen:
                return True
        return False

    def _libre(self, x, y):
        r = self.RADIO
        if x < r or y < r or x > self.ARENA - r or y > self.ARENA - r:
            return False
        return not self._en_obstaculo(x, y, margen=r)

    # -- interfaz Robot ------------------------------------------------
    def mover(self, direccion):
        self.orden = direccion

    def disparar(self, potencia):
        rad = math.radians(self.rumbo)
        dx, dy = math.cos(rad), math.sin(rad)
        self.bolas.append({
            "x": self.x + dx * self.RADIO,
            "y": self.y + dy * self.RADIO,
            "dx": dx,
            "dy": dy,
            "restante": self.ALCANCE_MAX * potencia / 100.0,
        })

    def distancia_cm(self):
        rad = math.radians(self.rumbo)
        dx, dy = math.cos(rad), math.sin(rad)
        for paso in range(1, RANGO_SENSOR_CM + 1):
            px, py = self.x + dx * paso, self.y + dy * paso
            if self._fuera(px, py) or self._en_obstaculo(px, py):
                return paso
        return None

    def actualizar(self, dt):
        self.t += dt
        rad = math.radians(self.rumbo)
        if self.orden == "izquierda":
            self.rumbo -= self.V_GIRO * dt
        elif self.orden == "derecha":
            self.rumbo += self.V_GIRO * dt
        elif self.orden in ("adelante", "atras"):
            signo = 1 if self.orden == "adelante" else -1
            nx = self.x + signo * math.cos(rad) * self.V_LINEAL * dt
            ny = self.y + signo * math.sin(rad) * self.V_LINEAL * dt
            if self._libre(nx, ny):
                self.x, self.y = nx, ny
        self._mover_bolas(dt)
        self.impactos = [i for i in self.impactos if i[2] > self.t]

    def _mover_bolas(self, dt):
        for b in self.bolas[:]:
            avance = min(self.V_BOLA * dt, b["restante"])
            pasos = max(1, math.ceil(avance))
            for _ in range(pasos):
                b["x"] += b["dx"] * avance / pasos
                b["y"] += b["dy"] * avance / pasos
                if self._fuera(b["x"], b["y"]) or self._en_obstaculo(b["x"], b["y"]):
                    b["restante"] = 0
                    break
            b["restante"] -= avance
            if b["restante"] <= 0.01:
                self.bolas.remove(b)
                self.impactos.append((b["x"], b["y"], self.t + 2.5))


class RobotSPIKE(Robot):
    """
    PENDIENTE: conexión real con el hub (USB o Bluetooth).

    Debe implementar los mismos métodos que RobotSimulado:
      mover(direccion)  -> enviar la orden a los motores A y E
      disparar(potencia)-> girar el motor C una rotación
      distancia_cm()    -> leer el sensor del puerto D
    Cuando esté listo, en main() se reemplaza RobotSimulado() por RobotSPIKE().
    """

    def __init__(self):
        raise NotImplementedError("La conexión con el robot real aún no está implementada.")


# ======================================================================
# Ventana
# ======================================================================
TECLAS = {
    "w": "adelante", "Up": "adelante",
    "s": "atras", "Down": "atras",
    "a": "izquierda", "Left": "izquierda",
    "d": "derecha", "Right": "derecha",
}


class App:
    def __init__(self, root, robot):
        self.root = root
        self.robot = robot

        self.esquivar = tk.BooleanVar(value=False)
        self.potencia = tk.IntVar(value=70)
        self.umbral = tk.IntVar(value=25)

        self.dir_actual = "detener"
        self.girando = False
        self.tecla_activa = None
        self.t_disparo = -10.0
        self.dist = None
        self.botones_mov = []

        root.title("Panel de control - Cañón lanzador")
        root.configure(bg=BG)
        root.resizable(False, False)

        self._construir()
        self._atar_teclas()

        self.ultimo = time.monotonic()
        self.log("Panel iniciado en modo simulación.")
        self.tick()

    # -- construcción --------------------------------------------------
    def _tarjeta(self, padre, titulo):
        marco = tk.Frame(padre, bg=PANEL, highlightthickness=1, highlightbackground=BORDE)
        marco.pack(fill="x", pady=(0, 10))
        tk.Label(marco, text=titulo, bg=PANEL, fg=INK,
                 font=(FUENTE, 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        cuerpo = tk.Frame(marco, bg=PANEL)
        cuerpo.pack(fill="x", padx=12, pady=(0, 12))
        return cuerpo

    def _construir(self):
        cab = tk.Frame(self.root, bg=BG)
        cab.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 8))
        tk.Label(cab, text="Cañón lanzador", bg=BG, fg=INK,
                 font=(FUENTE, 18, "bold")).pack(side="left")
        tk.Label(cab, text="Modo simulación: sin robot conectado", bg=AMARILLO, fg=INK,
                 font=(FUENTE, 9), padx=10, pady=3).pack(side="right")

        izq = tk.Frame(self.root, bg=BG)
        izq.grid(row=1, column=0, sticky="n", padx=(16, 8))
        der = tk.Frame(self.root, bg=BG)
        der.grid(row=1, column=1, sticky="n", padx=(8, 16))

        # --- Movimiento
        mov = self._tarjeta(izq, "Movimiento")
        pad = tk.Frame(mov, bg=PANEL)
        pad.pack()
        self._boton_mov(pad, "▲", "adelante", 0, 1)
        self._boton_mov(pad, "◀", "izquierda", 1, 0)
        self._boton_mov(pad, "▶", "derecha", 1, 2)
        self._boton_mov(pad, "▼", "atras", 2, 1)
        tk.Button(pad, text="■", width=4, height=2, font=(FUENTE, 14), bg=ROSA, fg="white",
                  activebackground="#B02A6B", activeforeground="white", relief="flat",
                  takefocus=0, command=lambda: self.ordenar("detener")
                  ).grid(row=1, column=1, padx=3, pady=3)
        tk.Label(mov, text="Mantén presionado para avanzar. Teclado: W A S D o flechas.",
                 bg=PANEL, fg=MUTED, font=(FUENTE, 8)).pack(pady=(6, 0))

        # --- Disparo
        disp = self._tarjeta(izq, "Disparo")
        self.lbl_pot = tk.Label(disp, text="Potencia: 70 %", bg=PANEL, fg=INK, font=(FUENTE, 10))
        self.lbl_pot.pack(anchor="w")
        tk.Scale(disp, from_=10, to=100, orient="horizontal", variable=self.potencia,
                 showvalue=False, length=270, bg=PANEL, troughcolor=BORDE,
                 highlightthickness=0, takefocus=0,
                 command=lambda v: self.lbl_pot.config(text=f"Potencia: {int(float(v))} %")
                 ).pack(anchor="w", pady=(0, 8))
        tk.Button(disp, text="Disparar", font=(FUENTE, 14, "bold"), bg=AMARILLO, fg=INK,
                  activebackground=AMARILLO_OSCURO, relief="flat", pady=8, takefocus=0,
                  command=self.disparar).pack(fill="x")
        tk.Label(disp, text="Teclado: barra espaciadora.", bg=PANEL, fg=MUTED,
                 font=(FUENTE, 8)).pack(anchor="w", pady=(6, 0))

        # --- Esquivar
        esq = self._tarjeta(izq, "Esquivar obstáculos")
        tk.Checkbutton(esq, text="Modo automático (avanza y gira solo)", variable=self.esquivar,
                       command=self._cambio_esquivar, bg=PANEL, fg=INK, activebackground=PANEL,
                       font=(FUENTE, 10), takefocus=0).pack(anchor="w")
        self.lbl_umbral = tk.Label(esq, text="Reacciona a menos de 25 cm", bg=PANEL, fg=INK,
                                   font=(FUENTE, 10))
        self.lbl_umbral.pack(anchor="w", pady=(8, 0))
        tk.Scale(esq, from_=15, to=60, orient="horizontal", variable=self.umbral,
                 showvalue=False, length=270, bg=PANEL, troughcolor=BORDE,
                 highlightthickness=0, takefocus=0,
                 command=lambda v: self.lbl_umbral.config(
                     text=f"Reacciona a menos de {int(float(v))} cm")
                 ).pack(anchor="w")

        # --- Sensor
        sen = self._tarjeta(der, "Sensor de distancia")
        self.lbl_dist = tk.Label(sen, text="-", bg=PANEL, fg=INK, font=(FUENTE, 28, "bold"))
        self.lbl_dist.pack(anchor="w")
        self.barra = tk.Canvas(sen, width=320, height=14, bg=BORDE, highlightthickness=0)
        self.barra.pack(anchor="w", pady=(4, 0))

        # --- Vista de la simulación
        sim = self._tarjeta(der, "Vista de la simulación")
        lado = int(RobotSimulado.ARENA * ESC)
        self.canvas = tk.Canvas(sim, width=lado, height=lado, bg="#E3ECEA",
                                highlightthickness=1, highlightbackground=BORDE)
        self.canvas.pack()
        tk.Label(sim, text="Vista desde arriba de una arena de 200 x 200 cm.",
                 bg=PANEL, fg=MUTED, font=(FUENTE, 8)).pack(anchor="w", pady=(6, 0))

        # --- Registro
        reg = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground=BORDE)
        reg.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        tk.Label(reg, text="Registro de eventos", bg=PANEL, fg=INK,
                 font=(FUENTE, 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.txt = tk.Text(reg, height=6, width=60, bg=PANEL, fg=INK, relief="flat",
                           font=("Consolas", 9), state="disabled", takefocus=0)
        self.txt.pack(fill="x", padx=12, pady=(0, 12))

    def _boton_mov(self, padre, texto, direccion, fila, col):
        b = tk.Button(padre, text=texto, width=4, height=2, font=(FUENTE, 14), bg=TEAL,
                      fg="white", activebackground=TEAL_OSCURO, activeforeground="white",
                      relief="flat", takefocus=0)
        b.grid(row=fila, column=col, padx=3, pady=3)
        b.bind("<ButtonPress-1>", lambda e: self.ordenar(direccion))
        b.bind("<ButtonRelease-1>", lambda e: self.ordenar("detener"))
        self.botones_mov.append(b)

    def _atar_teclas(self):
        self.root.bind("<KeyPress>", self._tecla_abajo)
        self.root.bind("<KeyRelease>", self._tecla_arriba)

    # -- acciones ------------------------------------------------------
    def log(self, mensaje):
        hora = time.strftime("%H:%M:%S")
        self.txt.config(state="normal")
        self.txt.insert("end", f"[{hora}] {mensaje}\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def ordenar(self, direccion):
        """Orden manual del usuario. Se ignora si el modo automático está activo."""
        if self.esquivar.get():
            return
        self._enviar(direccion)

    def _enviar(self, direccion):
        if direccion == self.dir_actual:
            return
        self.dir_actual = direccion
        self.log("Robot detenido" if direccion == "detener" else f"Moviendo: {direccion}")
        self.robot.mover(direccion)

    def disparar(self):
        ahora = time.monotonic()
        if ahora - self.t_disparo < ENFRIAMIENTO_S:
            return
        self.t_disparo = ahora
        potencia = self.potencia.get()
        self.robot.disparar(potencia)
        self.log(f"Disparo con potencia {potencia} %")

    def _cambio_esquivar(self):
        activo = self.esquivar.get()
        for b in self.botones_mov:
            b.config(state="disabled" if activo else "normal")
        self.girando = False
        if activo:
            self.log("Modo esquivar activado")
        else:
            self.log("Modo esquivar desactivado")
            self._enviar("detener")

    def _tecla_abajo(self, e):
        k = e.keysym.lower() if len(e.keysym) == 1 else e.keysym
        if k in TECLAS:
            self.tecla_activa = k
            self.ordenar(TECLAS[k])
        elif k == "space":
            self.disparar()

    def _tecla_arriba(self, e):
        k = e.keysym.lower() if len(e.keysym) == 1 else e.keysym
        if k == self.tecla_activa:
            self.tecla_activa = None
            self.ordenar("detener")

    def _logica_esquivar(self):
        umbral = self.umbral.get()
        d = self.dist
        if self.girando:
            if d is None or d > umbral + HISTERESIS_CM:
                self.girando = False
                self._enviar("adelante")
            else:
                self._enviar("derecha")
        elif d is not None and d < umbral:
            self.girando = True
            self.log(f"Obstáculo a {d} cm: girando")
            self._enviar("derecha")
        else:
            self._enviar("adelante")

    # -- ciclo principal -----------------------------------------------
    def tick(self):
        ahora = time.monotonic()
        dt = min(ahora - self.ultimo, 0.1)
        self.ultimo = ahora

        self.dist = self.robot.distancia_cm()
        if self.esquivar.get():
            self._logica_esquivar()
        self.robot.actualizar(dt)
        self.dist = self.robot.distancia_cm()

        self._pintar_sensor()
        self._dibujar()
        self.root.after(50, self.tick)

    def _pintar_sensor(self):
        d = self.dist
        umbral = self.umbral.get()
        ancho = int(self.barra["width"])
        self.barra.delete("all")
        if d is None:
            self.lbl_dist.config(text="Sin objeto", fg=MUTED)
            fraccion, color = 1.0, TEAL
        else:
            self.lbl_dist.config(text=f"{d} cm", fg=ALERTA if d < umbral else INK)
            fraccion, color = min(d, RANGO_SENSOR_CM) / RANGO_SENSOR_CM, (ALERTA if d < umbral else TEAL)
        self.barra.create_rectangle(0, 0, ancho * fraccion, 14, fill=color, width=0)
        x = ancho * umbral / RANGO_SENSOR_CM
        self.barra.create_line(x, 0, x, 14, fill=INK, width=2)

    def _dibujar(self):
        r = self.robot
        if not r.es_simulacion:
            return
        c = self.canvas
        c.delete("all")
        for x1, y1, x2, y2 in r.obstaculos:
            c.create_rectangle(x1 * ESC, y1 * ESC, x2 * ESC, y2 * ESC,
                               fill="#AEBDBA", outline="#8A9C99")

        rad = math.radians(r.rumbo)
        largo = self.dist if self.dist is not None else RANGO_SENSOR_CM
        c.create_line(r.x * ESC, r.y * ESC,
                      (r.x + math.cos(rad) * largo) * ESC, (r.y + math.sin(rad) * largo) * ESC,
                      fill=TEAL, dash=(4, 3))

        for ix, iy, _ in r.impactos:
            c.create_oval((ix - 3) * ESC, (iy - 3) * ESC, (ix + 3) * ESC, (iy + 3) * ESC,
                          fill=ROSA, outline="")
        for b in r.bolas:
            c.create_oval((b["x"] - 2.5) * ESC, (b["y"] - 2.5) * ESC,
                          (b["x"] + 2.5) * ESC, (b["y"] + 2.5) * ESC, fill=AMARILLO, outline=INK)

        puntos = []
        for giro, radio in ((0, r.RADIO * 1.4), (140, r.RADIO), (-140, r.RADIO)):
            a = math.radians(r.rumbo + giro)
            puntos += [(r.x + math.cos(a) * radio) * ESC, (r.y + math.sin(a) * radio) * ESC]
        c.create_polygon(puntos, fill=AMARILLO, outline=INK, width=2)


def main():
    root = tk.Tk()
    robot = RobotSimulado() 
    App(root, robot)
    root.mainloop()


if __name__ == "__main__":
    main()