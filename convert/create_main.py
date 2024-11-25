import os
import logging
import aiofiles
from util.exception import MainCreationError

MAIN_CLASS_NAME = "DemoApplication.java"
MAIN_CLASS_PATH = 'java/demo/src/main/java/com/example/demo'
MAIN_CLASS_TEMPLATE = """
package com.example.demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class DemoApplication {

    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }

}
"""

# 역할: Spring Boot 애플리케이션의 시작점이 되는 메인 클래스 파일을 생성합니다.
#      이 메인 클래스는 Spring Boot 애플리케이션을 실행하는데 필수적인 파일입니다.
# 매개변수: 없음
# 반환값: 없음
async def start_main_processing():
    
    logging.info("메인 클래스 생성을 시작합니다.")

    try:
        # * 메인 클래스 파일을 저장할 디렉토리 경로를 설정합니다.
        base_directory = os.getenv('DOCKER_COMPOSE_CONTEXT')
        if base_directory:
            main_class_directory = os.path.join(base_directory, MAIN_CLASS_PATH)
        else:
            parent_workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            main_class_directory = os.path.join(parent_workspace_dir, 'target', MAIN_CLASS_PATH)
        os.makedirs(main_class_directory, exist_ok=True)  


        # * 메인 클래스를 파일로 생성합니다.
        main_class_path = os.path.join(main_class_directory, MAIN_CLASS_NAME)  
        async with aiofiles.open(main_class_path, 'w', encoding='utf-8') as file:  
            await file.write(MAIN_CLASS_TEMPLATE)  
            logging.info(f"메인 클래스가 생성되었습니다.\n")  
        
    except Exception:
        err_msg = "스프링부트의 메인 클래스를 생성하는 도중 오류가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise MainCreationError(err_msg)