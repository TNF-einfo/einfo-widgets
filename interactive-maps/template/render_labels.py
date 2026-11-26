#!/usr/bin/env python3
"""核對地名分佈：都縣界+23區界+pin+全部地名（基準位置，未套位移）畫出來看。"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont
B = r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad"
kanto = json.load(open(B+r"\kanto.geojson", encoding="utf-8"))
ku = json.load(open(B+r"\tokyo_ku.geojson", encoding="utf-8"))
font = ImageFont.truetype(r"C:\Windows\Fonts\msjh.ttc", 15)
fontb = ImageFont.truetype(r"C:\Windows\Fonts\msjh.ttc", 21)

spots = [(1,35.997475,139.8114455),(2,36.0113203,139.5091906),(3,35.7280647,139.7070079),
         (4,35.6349494,139.7958032),(5,35.5838724,139.7603075),(6,35.7113,139.8678)]
places = [("埼玉縣",35.95,139.56,1),("千葉縣",35.66,139.905,1),("神奈川縣",35.52,139.62,1),("東京灣",35.575,139.85,1),
 ("春日部市",35.975,139.752,0),("越谷市",35.891,139.790,0),("草加市",35.825,139.805,0),("川口市",35.808,139.724,0),
 ("埼玉市",35.906,139.624,0),("上尾市",35.977,139.593,0),("北本市",36.027,139.530,0),("三鄉市",35.833,139.872,0),
 ("松戶市",35.788,139.903,0),("流山市",35.856,139.902,0),("川崎市",35.531,139.703,0),("武藏野市",35.718,139.566,0),
 ("千代田區",35.694,139.753,0),("中央區",35.667,139.772,0),("港區",35.658,139.752,0),("新宿區",35.694,139.703,0),
 ("文京區",35.708,139.752,0),("台東區",35.713,139.780,0),("墨田區",35.710,139.801,0),("江東區",35.673,139.817,0),
 ("品川區",35.609,139.730,0),("目黑區",35.641,139.698,0),("大田區",35.561,139.716,0),("世田谷區",35.646,139.653,0),
 ("澀谷區",35.664,139.698,0),("中野區",35.707,139.664,0),("杉並區",35.700,139.636,0),("豐島區",35.726,139.716,0),
 ("北區",35.753,139.734,0),("荒川區",35.736,139.783,0),("板橋區",35.751,139.709,0),("練馬區",35.735,139.652,0),
 ("足立區",35.775,139.805,0),("葛飾區",35.744,139.847,0),("江戶川區",35.706,139.868,0)]

W,H=1120,1000; LNG0,LNG1,LAT0,LAT1=139.42,139.98,35.48,36.06
def px(lng,lat): return ((lng-LNG0)/(LNG1-LNG0)*W,(1-(lat-LAT0)/(LAT1-LAT0))*H)
img=Image.new("RGB",(W,H),(182,211,223)); d=ImageDraw.Draw(img)
for f in kanto["features"]:
    for poly in f["geometry"]["coordinates"]:
        for ri,ring in enumerate(poly):
            d.polygon([px(x,y) for x,y in ring], fill=(244,238,224) if ri==0 else (182,211,223), outline=(200,169,143))
for f in ku["features"]:
    for poly in f["geometry"]["coordinates"]:
        for ring in poly:
            d.line([px(x,y) for x,y in ring], fill=(176,162,176), width=1)
def ctr(t,fo): b=d.textbbox((0,0),t,font=fo); return b[2]-b[0],b[3]-b[1]
for t,lat,lng,big in places:
    x,y=px(lng,lat); fo=fontb if big else font; w,h=ctr(t,fo)
    d.text((x-w/2,y-h/2),t,fill=(120,100,70) if big else (110,120,110),font=fo)
for n,lat,lng in spots:
    x,y=px(lng,lat); r=12
    d.ellipse([x-r,y-r,x+r,y+r],fill=(220,30,60),outline="white",width=3)
    d.text((x-4,y-8),str(n),fill="white",font=font)
p=B+r"\labels_check.png"; img.save(p); print("saved",p)
