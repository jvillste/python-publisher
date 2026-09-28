# Title: Demo

import random
import math

paikka = [300, 200]

def piirra():
    screen.clear("#0f172a")
    screen.circle(paikka[0], paikka[1], 10, "#facc15")

def paivita(aika_ms):
    paikka[0] = math.sin(aika_ms / 300) * 200 + 300
    piirra()

screen.on_frame(paivita)
