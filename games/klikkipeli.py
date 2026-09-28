# Title: Klikkipeli (grafiikka-demo)
"""Klikkaa keltaista palloa!

Tämä peli ei lue tekstikomentoja lainkaan, vaan käyttää screen-objektia:
se piirtää ruudulle ja reagoi hiiren klikkauksiin, näppäinpainalluksiin ja
animaatiokehysiin.
"""

import random

pisteet = 0
sade = 24
paikka = [300, 200]
nopeus = [120, 90]
edellinen_aika = None


def piirra():
    screen.clear("#0f172a")
    screen.circle(paikka[0], paikka[1], sade, "#facc15")
    screen.text(8, 8, "Pisteet: " + str(pisteet), "#e2e8f0", 14)
    screen.text(8, screen.height - 24,
                "Klikkaa palloa!  Välilyönti = uusi pallo,  Esc = lopeta",
                "#94a3b8", 12)


def paivita(aika_ms):
    global edellinen_aika
    if edellinen_aika is None:
        edellinen_aika = aika_ms
        return
    sekuntia = (aika_ms - edellinen_aika) / 1000
    edellinen_aika = aika_ms
    paikka[0] += nopeus[0] * sekuntia
    paikka[1] += nopeus[1] * sekuntia
    if paikka[0] < sade or paikka[0] > screen.width - sade:
        nopeus[0] = -nopeus[0]
    if paikka[1] < sade or paikka[1] > screen.height - sade:
        nopeus[1] = -nopeus[1]
    piirra()


def klikkaus(x, y):
    global pisteet
    dx = x - paikka[0]
    dy = y - paikka[1]
    if dx * dx + dy * dy <= sade * sade:
        pisteet = pisteet + 1
        nopeus[0] = nopeus[0] * 1.1
        nopeus[1] = nopeus[1] * 1.1
        print("Osuma! Pisteet:", pisteet)
    else:
        print("Ohi meni.")


def näppäin(näppäin_nimi):
    global edellinen_aika
    if näppäin_nimi == "Escape":
        screen.on_frame(None)
        screen.on_mouse_click(None)
        screen.clear("#0f172a")
        screen.text(8, screen.height // 2 - 10,
                    "Peli loppui! Pisteet: " + str(pisteet), "#f87171", 20)
        print("Kiitos pelaamisesta! Loppupisteet:", pisteet)
    if näppäin_nimi == " ":
        paikka[0] = random.randint(sade, screen.width - sade)
        paikka[1] = random.randint(sade, screen.height - sade)
        nopeus[0] = random.choice([-1, 1]) * 120
        nopeus[1] = random.choice([-1, 1]) * 90
        edellinen_aika = None


piirra()
screen.on_mouse_click(klikkaus)
screen.on_key_press(näppäin)
screen.on_frame(paivita)
print("Peli alkoi! Klikkaa keltaista palloa.")
