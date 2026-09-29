// Title: Seikkailu (Odin)
package main

import console "lib:console"

main :: proc() {
	paikka := "olkkari"
	hp := 10
	for {
		console.println("hyvinvointisi on", hp, ".")
		if paikka == "olkkari" {
			console.println("olet olkkarissa, siellä on \"ajattele että tässä on hieno kuvaus paikasta\" voit mennä keittiöön vastaamalla \"keittiöön\"")
		}
		if paikka == "keittiö" {
			console.println("olet keittiössä, siellä on \"ajattele että tässä on tosi tosi TOSI hieno kuvaus paikasta\" voit mennä olkkariin vastaamalla \"olkkariin\"")
		}
		vastaus, kunnossa := console.input("anna komento: ")
		if !kunnossa {
			break
		}
		if vastaus == "keittiöön" && paikka == "olkkari" {
			paikka = "keittiö"
		}
		if vastaus == "olkkariin" {
			paikka = "olkkari"
		}
		if vastaus == "lopeta" {
			break
		}
	}
	console.println("Loppu.")
}
