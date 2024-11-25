import os
import logging
import aiofiles
from util.exception import PomXmlCreationError

POM_FILE_NAME = "pom.xml"
POM_PATH = 'java/demo'
POM_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.2</version>
        <relativePath/> <!-- lookup parent from repository -->
    </parent>
    <groupId>com.example</groupId>
    <artifactId>demo</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <name>demo</name>
    <description>demo project for Spring Boot</description>
    <url/>
    <licenses>
        <license/>
    </licenses>
    <developers>
        <developer/>
    </developers>
    <scm>
        <connection/>
        <developerConnection/>
        <tag/>
        <url/>
    </scm>
    <properties>
        <java.version>17</java.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-rest</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""


# 역할: Spring Boot 프로젝트의 필수 설정 파일인 pom.xml을 생성합니다.
#      이 파일은 프로젝트의 의존성과 빌드 설정을 관리합니다.
# 매개변수: 없음
# 반환값: 없음
async def start_pomxml_processing():
    
    logging.info("pom.xml 생성을 시작합니다.")
    
    try:       
        # * pom.xml 파일을 저장할 디렉토리를 생성합니다.
        base_directory = os.getenv('DOCKER_COMPOSE_CONTEXT')
        if base_directory:
            pom_xml_directory = os.path.join(base_directory, POM_PATH)
        else:
            parent_workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            pom_xml_directory = os.path.join(parent_workspace_dir, 'target', POM_PATH)
        os.makedirs(pom_xml_directory, exist_ok=True)


        # * pom.xml 파일로 생성합니다.
        pom_xml_path = os.path.join(pom_xml_directory, POM_FILE_NAME)  
        async with aiofiles.open(pom_xml_path, 'w', encoding='utf-8') as file:  
            await file.write(POM_XML_TEMPLATE)  
            logging.info(f"Pom.xml이 생성되었습니다.\n")

    except Exception:
        err_msg = "스프링부트의 Pom.xml 파일을 생성하는 도중 오류가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise PomXmlCreationError(err_msg)