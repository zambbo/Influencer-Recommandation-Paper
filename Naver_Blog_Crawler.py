from selenium import webdriver
import urllib.request
import time
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import pandas as pd
import requests
import time
from datetime import date
import re
import xml.etree.ElementTree as ET
import numpy as np
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from konlpy.tag import Okt
from collections import Counter
import pytesseract
import io
from PIL import Image
import json

class NaverBlogCrawler:
    
    def __init__(self,_itemname=None,_blog_url_list = None):
        self.itemname = _itemname
        self.blog_url_list = _blog_url_list
        if _itemname:
            self.post_df = pd.DataFrame(columns=("Title","Blogger","Post URL","Post","Image num","sticker num","gif num","Paragraph num","Comment num","Video num","weekly viewer mean","Sympathy num",'AD','Posting Date','Buddy num','Total visit','Blog category'))
        elif _blog_url_list:
            self.post_df = pd.DataFrame(columns=("Post URL","Post","Image num","sticker num","gif num","Paragraph num","Comment num","Video num","weekly viewer mean","Sympathy num",'AD','Posting Date','Buddy num','Total visit','Blog category'))
        else:
            self.post_df = None

        #광고성 글이라고 판단할 키워드 리스트
        self.keyword_list = ['협찬','제공','증정','지원','원고료','회원가입','업체']
        #광고성 글이 아니라고 판단할 키워드 리스트
        self.notad_keyword_list = ['내돈내산','내돈','REAL']
        
    #크롬 드라이버로 특정 제품 검색 후 모든 블로그 글 area 스크롤
    def getPostsByItem(self):
        driver = webdriver.Chrome("./chromedriver")
        driver.implicitly_wait(3)

        #서치할 링크 만들기
        item_search_url = f'https://search.naver.com/search.naver?query={self.itemname}&nso=&where=blog&sm=tab_opt'

        #링크 접속
        driver.get(item_search_url)

        #모든 블로그 글들을 로딩하기 위해 페이지 무한 스크롤
        last_height=driver.execute_script("return document.body.scrollHeight")
        # num=0
        sp_blog=60
        while True:
            # 페이지 맨 아래로 스크롤바 이동
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                #페이지가 전부 로딩될때까지 wait
                WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#sp_blog_{sp_blog}")))
            except:
                break
            # 새로운 스크롤 높이 저장후 기존 스크롤 높이와 비교        
            new_height = driver.execute_script("return document.body.scrollHeight")
            sp_blog+=30
            #num+=1
            # 더이상 로딩할 블로그가 없으면 break
            if new_height == last_height:
                    break
            last_height = new_height
        time.sleep(1)

        #모든 블로그 글 area를 추출후 저장
        req=driver.page_source
        soup=BeautifulSoup(req,'html.parser')
        posts = soup.find_all("div", attrs={"class":"total_area"})
        return posts

    # 해당 포스트의 댓글 수 반환
    def getComment(self,soup):
        comment_css = "#commentCount"
        comment = soup.select_one(comment_css)
        comment_num = 0

        #댓글 갯수 확인
        if comment:
            if comment.text.strip().isdigit():
                comment_num = comment.text.strip()
            else:
                comment_num = 0
        else:
            comment_num = 0
        return comment_num
    
    # 해당 블로그의 본문 내용을 크롤링 하기 위해 #mainframe 안 링크로 접속
    def getInnerIFrameSoup(self,post_link):
        try:
            blog_base_url = "https://blog.naver.com"
            response = requests.get(post_link)
            soup = BeautifulSoup(response.text,'html.parser')
            blog_src_url = soup.select_one("#mainFrame")['src']
            response_IFrame = requests.get(blog_base_url+blog_src_url)
            IFrameLink = blog_base_url+blog_src_url
            soup = BeautifulSoup(response_IFrame.text,'html.parser')
        except:
            print("no mainFrame error")
            return None
        return (soup,IFrameLink)

    def getBDTVBC(self,_nickname):
        try:
            referer = f'https://m.blog.naver.com/{_nickname}'
            headers = {'referer':referer}
            m_blog_info_url = f'https://m.blog.naver.com/rego/BlogInfo.naver?blogId={_nickname}'
            res = requests.get(m_blog_info_url,headers=headers)
            text = res.text[res.text.find('\n')+1:-2]
            js = json.loads(text)
            buddy_num = js['result']['subscriberCount']
            totalVisitor_num = js['result']['totalVisitorCount']
            #todayVisitor_num = js['result']['dayVisitorCount']
            blogCategory_num = js['result']['blogDirectoryName']
        except:
            print('buddy error')
            return None
        return buddy_num,totalVisitor_num,blogCategory_num

    # def getBuddyNumFromNickName(self,_nick_name):
    #     url = f"https://blog.naver.com/{_nick_name}"
    #     response = requests.get(url)
    #     soup = BeautifulSoup(response.text,'html.parser')
    #     blog_src_url = soup.select_one("#mainFrame")['src']
    #     response_IFrame = requests.get("https://blog.naver.com"+blog_src_url)
    #     soup = BeautifulSoup(response_IFrame,'html.parser')
    #     blog_stats = soup.select_one('#blog-stat')
    #     blog_stats_widget = blog_stats.select_one('#widget-stat')
    #     buddy_num = blog_stats_widget.select_one('li:nth-child(2)').text
    #     return buddy_num
    # 해당 포스트의 공감수 반환
    def getSympnum(self,nick_name,post_link):
        pagenum = 1
        symp_num = 0
        while True:
            try:
                log_no = re.findall("logNo=[\d]+&",post_link)[0][6:-1]
                symp_url = f"https://blog.naver.com/SympathyHistoryList.naver?blogId={nick_name}&logNo={log_no}&currentPage={pagenum}"
                symp_res = requests.get(symp_url)
                symp_soup = BeautifulSoup(symp_res.text,'html.parser')
                pagenum = pagenum + 1
            except:
                print("no url error")
                break
            finally:
                symps = symp_soup.select('.list_sympathy li')
                if not symps:
                    # print('no symps error!',symp_num)
                    break
                symp_num = symp_num + len(symps)
        return symp_num
    
    # 해당 포스트의 단어 리스트로 저장
    def getNounList(self,_text):
        splt = Okt()
        noun = splt.nouns(_text)

        #의미 없는 조사는 제외
        for i,v in enumerate(noun):
            if v=='것'or v=='수' or v=='거' or v=='저':
                noun.pop(i)
        count = Counter(noun)
        count_list = []
        for text_count in count:
            count_list.append(text_count)
        return count_list
    
    def getPostLink(self,_soup):
        return _soup.find("a",attrs={"class":"api_txt_lines total_tit"})['href']

    
    def getPostDataFrame_blogUrls(self):
        post_df_idx=0
        post_num = len(self.blog_url_list)
        
        cur_post = 1
        for post_link in self.blog_url_list:
            print(f"\r{cur_post}/{post_num}",end='')
            cur_post = cur_post + 1

            try:
                soup,I_post_link = self.getInnerIFrameSoup(post_link)
                overlays = ".se-component.se-text.se-l-default"
                contents = soup.select(overlays)
                main_text = "".join([content.text for content in contents])
                main_text = main_text.replace("\n","").replace("\t","")
                text_num = len(main_text.split(" "))
                if text_num <=50:
                    continue
            except:
                continue

            #           댓글 수
            comment_num = self.getComment(soup)

            #         이미지 수
            image_list = soup.select(".se-module.se-module-image")
            sticker_list = soup.select(".se-module.se-module-sticker")
            image_num = len(image_list)
            sticker_num = len(sticker_list)

            gif_num =0
            for image in image_list:
                img_tag = image.select_one('a > img')
                if img_tag:
                    img_url = img_tag['src']
                    if re.findall(".GIF.",img_url):
                        gif_num+=1
            image_num-=gif_num
            #          비디오 수
            video_list = soup.select(".se-component.se-video")
            video_num = len(video_list)

            #           아이디
            nick_name = re.search("blogId=(.+)&logNo",I_post_link).group(1)

            #          공감 수
            symp_num = self.getSympnum(nick_name,I_post_link)

            #            블로그 일일 평균 방문자 수
            viewer_num_url = f'https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={nick_name}'
            viewer_num_response = requests.get(viewer_num_url)
            viewer_num_list = [int(node.get("cnt")) for node in ET.fromstring(viewer_num_response.text)]
            viewer_mean = np.mean(np.array(viewer_num_list))

            # 이웃 수
            try:
                buddy_num,total_visit,blogger_category = self.getBDTVBC(nick_name)
            except:
                buddy_num,total_visit,blogger_category = ('error','error','error')
            #광고 판단 기준
            ad=''
            #이미지와 스티커를 기준으로 광고 여부 판단
            for sel_list in [image_list,sticker_list]:
                if sel_list:
                    try:
                        sel_list[-2] = sel_list[-2]
                    except:
                        sel_list.append(sel_list[0])

                    for image in [sel_list[-1],sel_list[0],sel_list[-2]]:
                        img_tag = image.select_one('a > img')
                        # 이미지가 있을 경우
                        if img_tag:
                            #이미지의 link 저장
                            img_url = img_tag['src']
                            #레뷰 이미지가 포함되어 있으면 revu로 분류
                            if re.findall("www.revu.net",img_url):
                                ad = 'revu'
                                break
                            if re.findall("www.99das.com",img_url):
                                ad='99das'
                                break
                            if re.findall("storyn",img_url):
                                ad = 'storyn'
                                break
                            
                            #OCR 이용해 이미지내 텍스트 추출후 미리 선정한 키워드와 대조 비교
                            ad_img_response = requests.get(img_url)
                            img = Image.open(io.BytesIO(ad_img_response.content))
                            ad_text = pytesseract.image_to_string(img,lang='kor')
                            ad_text.replace("\n"," ")
                            ad_text.replace("\t"," ")
                            main_text += ad_text
                            #광고성 단어 포함시 img_ad 
                            for keyword in self.keyword_list:
                                if keyword in ad_text:
                                    ad ='img_ad'
                                    break
                            for keyword in self.notad_keyword_list:
                                if keyword in ad_text:
                                    ad=''
                                    break
                                        
                            #그 외에 광고일 가능성이 높은 image 마지막 이미지의 가로 세로 비율이 3:1일 경우 suspect로분류
                            try:
                                img_width = img_tag['data-width']
                                img_height = img_tag['data-height']
                                
                                if float(img_width)/float(img_height) > 3.0:
                                    ad='suspect'
                            except:
                                pass
            #텍스트를 기준으로 광고 여부 판단    
            title_text=main_text
            
            for keyword in self.keyword_list:
                if keyword in title_text:
                    ad='text_ad'
                    break
            for keyword in self.notad_keyword_list:
                if keyword in title_text:
                    ad=''
                    break
                    
        
            #블로그 작성 날짜
            posting_date_tag = soup.select_one(".se_publishDate")
            if posting_date_tag:
                posting_date = posting_date_tag.text
            else:
                posting_date = ''
            
            
            self.post_df.loc[post_df_idx] = [post_link,main_text,image_num,sticker_num,gif_num,text_num,comment_num,video_num,viewer_mean,symp_num,ad,posting_date,buddy_num,total_visit,blogger_category]
            post_df_idx+=1
            #print("-"*50)
        return self.post_df
    def savePostDf(self,posts):
        post_df_idx=0
        post_num = len(posts)
        
        cur_post = 1
        for post in posts:
            #print(post_df_idx)
            # 크롤링이 얼마나 진행되었는지 show
            print(f"\r{cur_post}/{post_num}",end='')
            cur_post = cur_post + 1

            #           포스트 제목
            post_title=post.find("a",attrs={"class":"api_txt_lines total_tit"}).get_text()
            #print("title :",post_title)

            #            포스트 블로거
            post_writer = post.find("a",attrs={"class":"sub_txt sub_name"}).get_text()
            #print("writer :",post_writer)

            #             포스트 링크
            post_link = post.find("a",attrs={"class":"api_txt_lines total_tit"})['href']
            #print("link :",post_link)

            #              포스트 본문
            try:
                soup,I_post_link = self.getInnerIFrameSoup(post_link)
                overlays = ".se-component.se-text.se-l-default"
                contents = soup.select(overlays)
                main_text = "".join([content.text for content in contents])
                main_text = main_text.replace("\n","").replace("\t","")
                text_num = len(main_text.split(" "))
                if text_num <=50:
                    continue
            except:
                continue

            #           댓글 수
            comment_num = self.getComment(soup)

            #         이미지 수
            image_list = soup.select(".se-module.se-module-image")
            sticker_list = soup.select(".se-module.se-module-sticker")
            image_num = len(image_list)
            sticker_num = len(sticker_list)

            gif_num =0
            for image in image_list:
                img_tag = image.select_one('a > img')
                if img_tag:
                    img_url = img_tag['src']
                    if re.findall(".GIF.",img_url):
                        gif_num+=1
            image_num-=gif_num
            #          비디오 수
            video_list = soup.select(".se-component.se-video")
            video_num = len(video_list)

            #           아이디
            nick_name = re.search("blogId=(.+)&logNo",I_post_link).group(1)

            #          공감 수
            symp_num = self.getSympnum(nick_name,I_post_link)

            # 이웃 수
            try:
                buddy_num,total_visit,blogger_category = self.getBDTVBC(nick_name)
            except:
                buddy_num,total_visit,blogger_category = ('error','error','error')
            #            블로그 일일 평균 방문자 수
            viewer_num_url = f'https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={nick_name}'
            viewer_num_response = requests.get(viewer_num_url)
            viewer_num_list = [int(node.get("cnt")) for node in ET.fromstring(viewer_num_response.text)]
            viewer_mean = np.mean(np.array(viewer_num_list))

            #광고 판단 기준
            ad=''
            #이미지와 스티커를 기준으로 광고 여부 판단
            for sel_list in [image_list,sticker_list]:
                if sel_list:
                    try:
                        sel_list[-2] = sel_list[-2]
                    except:
                        sel_list.append(sel_list[0])

                    for image in [sel_list[-1],sel_list[0],sel_list[-2]]:
                        img_tag = image.select_one('a > img')
                        # 이미지가 있을 경우
                        if img_tag:
                            #이미지의 link 저장
                            img_url = img_tag['src']
                            #레뷰 이미지가 포함되어 있으면 revu로 분류
                            if re.findall("www.revu.net",img_url):
                                ad = 'revu'
                                break
                            if re.findall("www.99das.com",img_url):
                                ad='99das'
                                break
                            if re.findall("storyn",img_url):
                                ad = 'storyn'
                                break
                            
                            #OCR 이용해 이미지내 텍스트 추출후 미리 선정한 키워드와 대조 비교
                            try:
                                ad_img_response = requests.get(img_url)
                                img = Image.open(io.BytesIO(ad_img_response.content))
                                ad_text = pytesseract.image_to_string(img,lang='kor')
                                ad_text.replace("\n"," ")
                                ad_text.replace("\t"," ")
                                main_text += ad_text
                            except:
                                pass
                            #광고성 단어 포함시 img_ad 
                            for keyword in self.keyword_list:
                                if keyword in ad_text:
                                    ad ='img_ad'
                                    break
                            for keyword in self.notad_keyword_list:
                                if keyword in ad_text:
                                    ad=''
                                    break
                                        
                            #그 외에 광고일 가능성이 높은 image 마지막 이미지의 가로 세로 비율이 3:1일 경우 suspect로분류
                            try:
                                img_width = img_tag['data-width']
                                img_height = img_tag['data-height']
                                
                                if float(img_width)/float(img_height) > 3.0:
                                    ad='suspect'
                            except:
                                pass
            #텍스트를 기준으로 광고 여부 판단    
            title_text=main_text+post_title
            
            for keyword in self.keyword_list:
                if keyword in title_text:
                    ad='text_ad'
                    break
            for keyword in self.notad_keyword_list:
                if keyword in title_text:
                    ad=''
                    break
                    
        
            #블로그 작성 날짜
            posting_date_tag = soup.select_one(".se_publishDate")
            if posting_date_tag:
                posting_date = posting_date_tag.text
            else:
                posting_date = ''
            
            
            self.post_df.loc[post_df_idx] = [post_title,post_writer,post_link,main_text,image_num,sticker_num,gif_num,text_num,comment_num,video_num,viewer_mean,symp_num,ad,posting_date,buddy_num,total_visit,blogger_category]
            post_df_idx+=1
            #print("-"*50)

    def getPostDataFrame_FromItemName(self):
        posts = self.getPostsByItem()
        self.savePostDf(posts)
        return self.post_df

def run():  
    start = time.time()   
    item_name = input("상품명을 검색하시오: ")

    crawler = NaverBlogCrawler(item_name)
    post_df = crawler.getPostDataFrame_FromItemName()
    print("interval : ",time.time()-start)

    item_name=item_name.replace("\"","")
    item_name=item_name.replace("+","")
    post_df.to_csv(item_name+date.today().isoformat()+'.csv')

    pd.set_option('display.max_rows',None)
    pd.set_option('display.max_columns',None)
    post_df
if __name__ == '__main__':
    run()