import requests
import bs4
from bs4 import BeautifulSoup
#import docx
import time
from datetime import date
import pdb
import os,sys
import concurrent.futures as cf
import pandas as pd
import re
import queue

url_template= 'https://tieba.baidu.com/f?kw=mad&ie=utf-8&tab=good&cid={}&pn={}'
otherprobq=queue.Queue()
picq=queue.Queue()
skiplist=[]

if os.path.isfile('skiplist.txt'):
    with open('skiplist.txt') as skipfile0:
        for line in skipfile0:
            skiplist.append(int(line.strip()))

def search_pages(area,n):
    links=[]
    for i in range(n):
        url=url_template.format(area,50*i)
        res=requests.get(url)
        soup=BeautifulSoup(res.text,'html.parser')
        page_list=soup.find_all(class_='threadlist_title pull_left j_th_tit')
        #pdb.set_trace()
        links.extend(extract_page_info(page_list))
        time.sleep(2)
    return links

def extract_page_info(pagelist):
    infolist=[]
    for item in pagelist:
        info={}
        info['title']=item.find(class_='j_th_tit')['title']
        info['address']='https://tieba.baidu.com'+item.find(class_='j_th_tit')['href']
        infolist.append(info)
    return infolist

def write_file_protected(dictuple):
    #pdb.set_trace()
    entrynum=str(dictuple[1])
    try:
        write_file(dictuple)
    except:
        print('something wrong with entry '+ entrynum)
        otherprobq.put(dictuple[1])

def write_file(dictuple):
    if dictuple[1] in skiplist:
        print('skipping entry %s'%dictuple[1])
        return
    
    area=dictuple[2]
    entryind=dictuple[1]
    dirname='area'+str(area)
    dirname2=dirname+'/'+'entry'+str(dictuple[1])+'_pic'
    if not os.path.isdir(dirname):
        os.mkdir(dirname)
    if not os.path.isdir(dirname2):
            os.mkdir(dirname2)

    imgcount=0
    link=dictuple[0]['address']+'?see_lz=1'
    #pdb.set_trace()
    try:
        r=requests.get(link,timeout=30)
        r.raise_for_status()
    except:
        print(dirname+'/'+'entry'+str(dictuple[1])+': status code: %s'%r.status_code)
        
    soup=BeautifulSoup(r.text,'html.parser')
    pagenum=int(soup.find(class_='l_reply_num').contents[2].text)
    title=soup.find(class_="core_title_txt pull-left text-overflow")['title']
    #pdb.set_trace()
    author=soup.find(class_=re.compile('p_author_name.*j_user_card')).text
    date0pre=soup.find(class_='post-tail-wrap').contents[2].text
    if date0pre=='1楼':
        date0 = soup.find(class_='post-tail-wrap').contents[3].text
    else:
        date0 = date0pre
    date1=date.today()
    with open(dirname+'/'+'entry'+str(dictuple[1])+'.md','w',encoding="utf-8") as fout:
        fout.write('# []()'+title+'  \n')
        fout.write( '原作者 百度贴吧:{} [原地址]({}) 首发时间:{}  \n最新获取时间:{}  \n'.format(author,dictuple[0]['address'],date0,date1))
        fout.write('  \n')

        for pn in range(pagenum):
            if pn>0:
                pagelink=link+'&pn=%s'%(pn+1)
                try:
                    r=requests.get(pagelink,timeout=30)
                    r.raise_for_status()
                except:
                    print(dirname+'/'+'entry'+str(dictuple[1])+': status code: %s'%r.status_code)
                    
                soup=BeautifulSoup(r.text,'html.parser')
            floors=soup.find_all(class_='d_post_content j_d_post_content')

            for floor in floors:
                #pdb.set_trace()
                for child in floor.children:
                    if child.name=='br':
                        fout.write('  \n')
                    elif child.name=='strong' or child.name=='span':
                        fout.write(child.text)
                    elif isinstance(child,bs4.element.NavigableString):
                        if child.strip()=='':
                            continue
                        #elif '就可以渲染输出了' in child.strip():
                        #    pdb.set_trace()
                        else:
                            fout.write(child.strip())
                    else:
                        try:
                            testchildclass=child['class']
                        except:
                            print('child class issue: %s'%child)
                            continue

                        if child['class']==['BDE_Flash']:
                            #pdb.set_trace()
                            fout.write('<原文此处有视频，建议到原地址观看>  \n')
                            try:
                                fout.write('<原文视频来源: %s>\n'%child['vsrc'])
                            except:
                                fout.write('<原文视频链接:暂时无法获取>\n')
                                continue
                            try:
                                picurl=child['vpic']
                            except:
                                continue
                            
                            imgname=dirname2+'/'+str(imgcount)+'.jpg'
                            
                            fout.write('\n![](/tb/'+imgname+')\n')
                            try:    
                                res=requests.get(picurl,timeout=30)    
                                with open(imgname,'wb') as fpic:
                                    fpic.write(res.content)
                            except:
                                print('something wrong saving '+imgname)
                                picq.put((imgname,picurl,dictuple[1]))
                            imgcount+=1
                            
                        elif child['class']==['j-no-opener-url'] or child['class']==["at"]:                
                            fout.write(child.text)
                        elif child['class']==['BDE_Image'] or child['class']==['BDE_Smiley']:
                            picurl=child['src']

                            imgname=dirname2+'/'+str(imgcount)+'.jpg'
                            if child['class']==['BDE_Image']:
                                fout.write('\n![](/tb/'+imgname+')\n')
                            else:
                                fout.write('![](/tb/'+imgname+')')
                            try:    
                                res=requests.get(picurl,timeout=30)    
                                with open(imgname,'wb') as fpic:
                                    fpic.write(res.content)
                            except:
                                print('something wrong saving '+imgname)
                                picq.put((imgname,picurl,dictuple[1]))
                                #if picq.qsize()>50:
                                #    sys.exit('Too many picture storing errors. Retry later.')
                            imgcount+=1

                fout.write('  \n\n')
            print('Processed entry %s, page %s/%s'%(str(dictuple[1]),pn+1,pagenum))
            time.sleep(1)

        
def write_links(filename,area,npage):
    if os.path.isfile(filename):
        return
    
    infolist=search_pages(area,npage)
    with open(filename,'w',encoding="utf-8") as fout:
        for item in infolist:
            fout.write('%s:%s\n'%(item['title'],item['address']))

def read_links(filename,area,npage):
    
    write_links(filename,area,npage)
    infolist=[]
    with open(filename,'r',encoding="utf-8") as flist:
        for line in flist:
            info={}
            info['title']=line.strip().split(':https')[0]
            info['address']='https'+line.strip().split(':https')[1]
            infolist.append(info)
    return infolist

ts=time.time()
infolist=read_links('tutoriallist.txt',4,3)            
#data=pd.DataFrame(dlist)
#data.to_excel('tutoriallist.xlsx')
finallist=infolist
indexlist=range(len(finallist))
arealist=[4 for i in range(len(finallist))]
inputlist=zip(finallist,indexlist,arealist)

debug=False
redo=True

if debug:
    redo = False
    
if not debug:
    with cf.ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(write_file_protected,inputlist)
else:
    write_file((infolist[15],15,4))

picRedoList=[]
otherRedoList=[]

while not picq.empty():
    picredoentry=picq.get()
    if not picredoentry in picRedoList: 
        picRedoList.append(picredoentry)

while not otherprobq.empty():
    otherredoentry=otherprobq.get()
    if not otherredoentry in otherRedoList: 
        otherRedoList.append(otherredoentry)

picFailList=[]
if redo:
    print("========================redoing some of the entries=======================================")
    piciter=0
    while len(picRedoList)>0 and piciter<100:

        picitem=picRedoList.pop()
        try:    
            res=requests.get(picitem[1],timeout=30)    
            with open(picitem[0],'wb') as fpic:
                fpic.write(res.content)
            print('Sucessfully added '+picitem[0])
        except:
            print('something wrong saving '+picitem[0])
            picRedoList.append(picitem)
            piciter+=1
            
    if piciter>=100:
        picFailList=[picnumber[2] for picnumber in picRedoList]
        print('Failing entries:',picFailList)
            
  #  with cf.ThreadPoolExecutor(max_workers=10) as executor:
  #      executor.map(write_file_protected,picRedoListFull)
    
  #  for item in otherRedoList:
  #      write_file((infolist[item],item,4))

with open('skiplist.txt','w') as skipfile:
    for i in range(len(finallist)):
        if not (i in picFailList or i in otherRedoList or debug):
            skipfile.write(str(i)+'\n')
            
    
print('time used %s'%(time.time()-ts))
