paikka = "olkkari"
hp = 10
vastaus = ""
while(vastaus != "lopeta"):
    print("hyvinvointisi on",hp+".")
    if(paikka == "olkkari"): print("olet olkkarissa, siellä on \"ajattele että tässä on hieno kuvaus paikasta\" voit mennä keittiöön vastaamalla \"keittiöön\"")
    vastaus = input("anna komento: ")
    if(vastaus == "keittiöön"):
        paikka = "keittiö"
