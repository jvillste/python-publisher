# Title: Seikkailu
paikka = "olkkari"
hp = 10
vastaus = ""
while(vastaus != "lopeta"):
    print("hyvinvointisi on",str(hp)+".")
    if(paikka == "olkkari"): print("olet olkkarissa, siellä on \"ajattele että tässä on hieno kuvaus paikasta\" voit mennä keittiöön vastaamalla \"keittiöön\"")
    if(paikka == "keittiö"): print("olet keittiössä, siellä on \"ajattele että tässä on tosi tosi TOSI hieno kuvaus paikasta\" voit mennä olkkariin vastaamalla \"olkkariin\"")
    vastaus = input("anna komento: ")
    if(vastaus == "keittiöön" and paikka == "olkkari"):
        paikka = "keittiö"
    if(vastaus == "olkkariin"):
        paikka = "olkkari"
