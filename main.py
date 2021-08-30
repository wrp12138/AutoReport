"""自动健康打卡"""
from __future__ import absolute_import

import ast
import configparser
import logging
import random
import re
import time

import requests
from bs4 import BeautifulSoup
from retrying import retry



# 固定链接，不建议修改
URL_MAP = {
    'HOST': 'https://ehall.hpu.edu.cn/infoplus/form/XSMRJKSB/start',
    'START': 'https://ehall.hpu.edu.cn/infoplus/interface/start',
    'ALIVE': 'https://ehall.hpu.edu.cn/infoplus/alive',
    'CAPTCHA': 'https://uia.hpu.edu.cn/sso/apis/v2/open/captcha?date=',
    'LOGIN': 'https://uia.hpu.edu.cn/cas/login',
    'RENDER': 'https://ehall.hpu.edu.cn/infoplus/interface/render',
    'PROCESS': 'https://ehall.hpu.edu.cn/infoplus/interface/instance/[id]/progress',
    'NEXTSTEP': 'https://ehall.hpu.edu.cn/infoplus/interface/listNextStepsUsers',
    'DOACTION': 'https://ehall.hpu.edu.cn/infoplus/interface/doAction',
    'CHECK': 'https://ehall.hpu.edu.cn/taskcenter/api/me/processes/done?limit=1&start=0',
    'API': 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=[ak]&client_secret=[sk]',
    'REQUEST_URL': 'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic'
}

# 请求头，可以按需更改
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/78.0.3904.108 Safari/537.36 QIHU 360EE'
}


class ReadConfig:
    """读取配置文件类"""

    def __init__(self, filename):
        """配置文件读取初始化"""
        self.config = configparser.ConfigParser()
        self.config['Basic'] = {
            'CHANGE_DATA': True,
            'CHANGE_ADDR': True,
            'IP_ADDR': '223.90.40.4'
        }
        self.config.read(filename, encoding='utf-8')

    def get_basic(self, param):
        """获取Basic配置"""
        value = self.config.get('Basic', param)
        return value

    def get_api(self, param):
        """获取API配置"""
        value = self.config.get('API', param)
        return value

    def get_user(self):
        """获取User配置"""
        value = self.config.items('User')
        return value


class Bot:
    """自动健康打卡类"""

    def __init__(self, config_file):
        """打卡初始化"""
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger('AutoReport')
        self.logger.info('程序启动中...')

        # 读取配置文件
        self.data = ReadConfig(config_file)
        self.addr = self.data.get_basic('LOCAL_ADDR')
        self.chaddr = self.data.get_basic('CHANGE_ADDR')
        self.ipaddr = self.data.get_basic('IP_ADDR')

        self.api_key = self.data.get_api('API_KEY')
        self.secret_key = self.data.get_api('SECRET_KEY')

        # 登录并打卡
        for user in self.data.get_user():
            self.sessions = requests.session()
            self.login(user)
            self.post(user)
            self.sessions.close()


    def login(self, user):
        """登录"""
        self.logger.info('%s开始登录中...', user[0])

        # 登录页面
        req = self.sessions.get(URL_MAP['HOST'], headers=HEADERS, timeout=5)
        req = self.sessions.get(req.url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(req.content, features="html.parser")
        form = soup.find_all('input', class_='for-form')

        # 验证码获取
        captcha = URL_MAP['CAPTCHA'] + str(int(round(time.time() * 1000)))
        req = self.sessions.get(captcha, headers=HEADERS, timeout=5)
        img = ast.literal_eval(req.content.decode('utf-8'))['img']
        self.logger.info('验证码获取成功!')

        # 验证码识别
        api = URL_MAP['API'].replace('[ak]', self.api_key).replace('[sk]', self.secret_key)
        response = requests.get(api)
        access_token = response.json()['access_token']
        request_url = URL_MAP['REQUEST_URL'] + "?access_token=" + access_token
        api_headers = {'content-type': 'application/x-www-form-urlencoded'}
        response = requests.post(request_url, data={'image': img}, headers=api_headers, timeout=5)
        captcha = response.json()['words_result'][0]['words']
        captcha = str(captcha.replace('=?', '')).split('+')
        captcha = sum(map(int, captcha))
        self.logger.info('验证码识别成功!')

        # 构造表单
        token = ast.literal_eval(req.content.decode('utf-8'))['token']
        account = ast.literal_eval(user[1])
        formdata = {
            'username': account[0],
            'password': account[1],
            '_eventId': 'submit',
            'token': token
        }
        formdata.update({f['name']: f['value'] for f in form})
        formdata.update({'captcha': captcha})

        # 登录
        req = self.sessions.post(URL_MAP['LOGIN'], headers=HEADERS, data=formdata, timeout=5)
        soup = BeautifulSoup(req.content, features='html.parser')
        errormes = soup.find('span', id='errormes')
        if errormes:
            self.logger.error(errormes['value'])
            raise Exception(errormes['value'])

        # 检测登录状态
        url = self.sessions.get(URL_MAP['HOST'], headers=HEADERS, timeout=5).url
        if not url == URL_MAP['HOST']:
            self.logger.error('登录失败, 未知错误!')
            raise Exception('登录失败, 未知错误!')
        else:
            self.logger.info('使用账号密码登录成功!')


    def post(self, user):
        """打卡"""
        self.logger.info('打卡进行中...')
        req = self.sessions.get(URL_MAP['HOST'], headers=HEADERS, timeout=5)
        soup = BeautifulSoup(req.content, features='html.parser')

        # 构造表单
        csrf = soup.find('meta', itemscope='csrfToken')['content']
        formdata = {
            'idc': 'XSMRJKSB',
            'release': '',
            'csrfToken': csrf,
            'formData': '{"_VAR_URL":"https://ehall.hpu.edu.cn/infoplus/form/XSMRJKSB/start","_VAR_URL_Attr":"{}"}'
        }
        req = self.sessions.post(URL_MAP['START'], headers=HEADERS, data=formdata, timeout=5)
        url = req.json()['entities'][0]

        # 构造表单
        stepid = int(re.findall(r'\d+', url)[0])
        self.logger.info('开始流程%s中...', stepid)
        formdata = {
            'stepId': stepid,
            'instanceId': '',
            'admin': 'false',
            'rand': random.random() * 999, 
            'width': '1747',
            'lang': 'zh',
            'csrfToken': csrf
        }
        HEADERS.update({'Referer': url})
        req = self.sessions.post(URL_MAP['RENDER'], headers=HEADERS, data=formdata, timeout=5)
        self.logger.info('已加载审批表!')
        form = req.json()['entities'][0]

        # 构造表单
        instanceid = form['step']['instanceId']
        formdata = {
            'stepId': stepid,
            'includingTop': 'true',
            'csrfToken': csrf,
            'lang': 'zh'
        }
        req = self.sessions.post(URL_MAP['PROCESS'].replace('[id]', instanceid), headers=HEADERS, data=formdata, timeout=5)
        self.logger.info('审批表处理中...')
        timestamp = req.json()['entities'][0]['remarks'][0]['assignTime']
        boundfields = ','.join(list(form['data'].keys()))

        # 构造表单
        postdata = form['data']
        account = ast.literal_eval(user[1])
        fixdata = {
            'fieldAN': '获取位置信息',
            'fieldDWAN': account[7],
            'fieldGRDW': account[5] + ',' + account[6] + ',' + '17',
            'fieldGRDW_Name': '自动获取',
            'fieldSQjhr': account[2],
            'fieldSQjhrlxdh': account[3],
            'fieldSQhjd': account[4],
            'fieldTXxjzdlx': '1',
            'fieldTXsfqgyq': '未去过重点疫区',
            'fieldTXsfqgyq_Name': '未去过重点疫区',
            'fieldTXsfjc': '2',
            'fieldTXcjtw': '36.6-36.9',
            'fieldTXcjtw_Name': '36.6-36.9',
            'fieldTXsfyc': '2',
            'fieldTXsfjcqk': '',
            'fieldTXsfjcqk_Name': '',
            'fieldTXzz': '',
            'fieldTXzz_Name': '',
            'fieldTXzz1': '',
            'fieldTXycjg': '',
            'fieldTXycjg_Name': '',
            'fieldTXycjgqt': '',
            'fieldTXzlcs': ''
        }
        postdata.update(fixdata)
        if self.addr == '1':
            fixdata = {
                'fieldTXsf': '410000',
                'fieldTXsf_Name': '河南省',
                'fieldTXcs': '410100',
                'fieldTXcs_Name': '郑州市',
                'fieldTXcs_Attr': '{\"_parent\":\"410000\"}',
                'fieldTXdq': '410103',
                'fieldTXdq_Name': '中原区',
                'fieldTXdq_Attr': '{\"_parent\":\"410100\"}',
                'fieldTXjtwz': '河南省郑州市中原区'
            }
        elif self.addr == '2':
            fixdata = {
                'fieldTXsf': '410000',
                'fieldTXsf_Name': '河南省',
                'fieldTXcs': '410800',
                'fieldTXcs_Name': '焦作市',
                'fieldTXcs_Attr': '{\"_parent\":\"410000\"}',
                'fieldTXdq': '410811',
                'fieldTXdq_Name': '山阳区',
                'fieldTXdq_Attr': '{\"_parent\":\"410800\"}',
                'fieldTXjtwz': '河南理工大学'
            }
        postdata.update(fixdata)
        if self.chaddr:
            postdata.update({'_VAR_ADDR': self.ipaddr})
        formdata = {
            'stepId': stepid,
            'actionId': 1,
            'formData': str(postdata),
            'timestamp': timestamp,
            'rand': random.random() * 999,
            'boundFields': boundfields,
            'csrfToken': csrf,
            'lang': 'zh'
        }
        req = self.sessions.post(URL_MAP['NEXTSTEP'], headers=HEADERS, data=formdata, timeout=5)
        if req.json()['ecode'] == 'SUCCEED':
            self.logger.info('健康打卡准备阶段, 成功!')
        else:
            raise Exception('健康打卡准备阶段, 失败!')

        # 构造表单
        formdata = {
            'actionId': 1,
            'formData': str(form['data']),
            'remark': '',
            'rand': random.random() * 999,
            'nextUsers': '{}',
            'stepId': stepid,
            'timestamp': timestamp,
            'boundFields': boundfields,
            'csrfToken': csrf,
            'lang': 'zh'
        }
        req = self.sessions.post(URL_MAP['DOACTION'], headers=HEADERS, data=formdata, timeout=5)
        if req.json()['ecode'] == 'SUCCEED':
            self.logger.info('健康打卡填报阶段, 成功!')
        else:
            raise Exception('健康打卡填报阶段, 失败!')
        self.check()


    def check(self):
        """打卡完毕后复检"""
        req = self.sessions.get(URL_MAP['CHECK'], headers=HEADERS, timeout=5)
        last_time = req.json()['entities'][0]['update']
        local_time = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(last_time))
        update = round(time.time()) - last_time
        if update > 5:
            self.logger.error('上次打卡完成于%ss前,打卡可能未成功!', update)
            raise Exception('打卡失败次数过多')
        else:
            self.logger.info('打卡完成于%s', local_time)


if __name__ == '__main__':
    BOT = Bot('config.ini')
