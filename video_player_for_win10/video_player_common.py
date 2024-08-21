import time
import json
import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

def setup_edge_driver():
    edge_options = Options()
    edge_options.add_argument("--start-maximized")  # 启动时最大化窗口
    edge_options.add_argument("--ignore-certificate-errors")  # 忽略证书错误
    edge_options.add_argument("--allow-insecure-localhost")  # 允许不安全的本地连接
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--disable-software-rasterizer")
    edge_options.add_argument("--no-sandbox")
    edge_options.add_argument("--disable-dev-shm-usage")
    edge_options.add_argument("--disable-hsts")

    # Edge浏览器驱动程序路径
    edge_service = EdgeService('msedgedriver.exe')
    # 启动Edge浏览器
    driver = webdriver.Edge(service=edge_service, options=edge_options)
    return driver
        
class SafetyError(Exception):
    pass

def play_videos(driver, start_index=0, last_known_good_time=0):

    # 打开视频汇总网页
    driver.get('https://strtv.dahuawang.com/b/a/list_dahua.shtml')

    # 获取所有视频链接
    video_links = driver.find_elements(By.CSS_SELECTOR, 'div.tit a')
    video_urls = [link.get_attribute('href') for link in video_links]

    for index in range(start_index, len(video_urls)):
        print(index)
        video_url = video_urls[index]
        retries = 0

        while retries < 3:
            try:
                # 打开视频链接
                driver.get(video_url)

                if "您的连接不是私密连接" in driver.page_source:
                    raise SafetyError

                # 等待视频元素加载
                video_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'video'))
                )

                # 尝试点击视频元素以播放
                ActionChains(driver).move_to_element(video_element).click().perform()

                # 使用JavaScript触发全屏
                driver.execute_script("""
                var video = arguments[0];
                if (video.requestFullscreen) {
                    video.requestFullscreen();
                } else if (video.mozRequestFullScreen) { // Firefox
                    video.mozRequestFullScreen();
                } else if (video.webkitRequestFullscreen) { // Chrome, Safari and Opera
                    video.webkitRequestFullscreen();
                } else if (video.msRequestFullscreen) { // IE/Edge
                    video.msRequestFullscreen();
                }
                """, video_element)

                # 如果有上次的播放进度，从上次的时间点继续播放
                if index == start_index:
                    print(f"starts from index:{index}, progress: {last_known_good_time}")
                    driver.execute_script(f"arguments[0].currentTime = {last_known_good_time};", video_element)

                # 等待视频开始播放
                WebDriverWait(driver, 10).until(
                    lambda d: driver.execute_script("return arguments[0].currentTime > 0", video_element)
                )

                # 获取视频时长
                video_duration = driver.execute_script("return arguments[0].duration;", video_element)
                print(video_duration)
                
                # 等待视频播放完成，并定期检查播放进度
                current_time = driver.execute_script("return arguments[0].currentTime;", video_element)
                
                check_interval = 5
                stuck_time_limit = 10  # 卡住时间限制
                last_progress_time = time.time()  # 上次播放进度更新的时间
                
                while current_time < video_duration:
                    time.sleep(check_interval)
                    previous_time = current_time
                    current_time = driver.execute_script("return arguments[0].currentTime;", video_element)
                    
                    # 如果播放进度有更新，则重置上次播放进度更新的时间
                    if current_time != previous_time:
                        last_progress_time = time.time()
                        last_known_good_time = current_time  # 更新已知的良好播放时间
                    else:
                        # 如果播放进度卡住，则抛出错误
                        if time.time() - last_progress_time > stuck_time_limit:
                            raise Exception(f"Playback progress stuck for more than {stuck_time_limit} seconds.")
                
                last_known_good_time = 0  # 视频已经播放完成，重置已知的良好播放时间
                break

            except SafetyError:
                print("Capture safety error.")
                raise SafetyError
            except Exception as e:
                with open('progress.json', 'w') as f:
                    json.dump({'index': index, 'time': last_known_good_time}, f)
                print(f"Saved progress for video {video_url} at {last_known_good_time} seconds")
                retries += 1
                print(f"Error playing video {video_url}: {e}. Retrying {retries}/3")
                time.sleep(5)
                start_index = index

                if retries >= 3:
                    # 保存当前进度
                    with open('progress.json', 'w') as f:
                        json.dump({'index': index, 'time': last_known_good_time}, f)
                    print(f"Saved progress for video {video_url} at {last_known_good_time} seconds")
                    driver.quit()
                    time.sleep(20)
                    sys.exit(0)

    driver.quit()
    sys.exit(0)

def play_video_with_error_handle(is_resume):
    progress_file = 'progress.json'
    if is_resume and os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            progress_data = json.load(f)
    else:
        progress_data = {}

    while True:
        try:
            driver = setup_edge_driver()
            play_videos(driver, start_index=progress_data.get('index', 0), last_known_good_time=progress_data.get('time', 0))
        except SafetyError:
            driver.quit()
            print("Restarting web driver")
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)