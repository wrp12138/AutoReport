pipeline {
  agent {
    any {
      reuseNode true
    }

  }
  stages {
    stage('检出') {
      steps {
        checkout([
          $class: 'GitSCM',
          branches: [[name: env.GIT_BUILD_REF]],
          userRemoteConfigs: [[
            url: env.GIT_REPO_URL,
            credentialsId: env.CREDENTIALS_ID
          ]]])
        }
      }
      stage('安装依赖') {
        steps {
          sh '''pip3.5 install --upgrade pip
pip3.5 install setuptools
pip3.5 install requests
pip3.5 install bs4
pip3.5 install configparser
pip3.5 install retrying'''
        }
      }
      stage('运行') {
        steps {
          sh 'python3 main.py'
        }
      }
    }
  }
