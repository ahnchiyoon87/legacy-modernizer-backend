import os
import logging
from util.exception import ConvertingError
from util.utility_tool import save_file


# ----- 설정 파일 템플릿 -----
POM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.2</version>
        <relativePath/>
    </parent>
    <groupId>com.example</groupId>
    <artifactId>{project_name}</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <name>{project_name}</name>
    <description>{project_name} project for Spring Boot</description>
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
            <groupId>com.oracle.database.jdbc</groupId>
            <artifactId>ojdbc11</artifactId>
            <scope>runtime</scope>
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

PROPERTIES_TEMPLATE = """spring.application.name={project_name}
spring.h2.console.enabled=true
spring.datasource.url=jdbc:h2:mem:testdb
spring.datasource.driverClassName=org.h2.Driver
spring.jpa.database-platform=org.hibernate.dialect.H2Dialect
spring.jpa.hibernate.ddl-auto=create-drop"""


# ----- 설정 파일 생성 관리 클래스 -----
class ConfigFilesGenerator:
    """
    Spring Boot 프로젝트의 설정 파일(pom.xml, application.properties)을 자동 생성하는 클래스
    Maven 의존성 설정과 애플리케이션 설정을 생성합니다.
    """

    def __init__(self, project_name: str, user_id: str):
        """
        ConfigFilesGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
        """
        self.project_name = project_name
        
        # 저장 경로 설정 (성능: 모든 경로를 __init__에서 한 번만 계산)
        base_dir = os.getenv('DOCKER_COMPOSE_CONTEXT') or os.path.abspath(os.path.join(__file__, '..', '..', '..'))
        base_path = os.path.join(base_dir, 'target', 'java', user_id)
        self.project_path = os.path.join(base_path, project_name)
        self.resources_path = os.path.join(self.project_path, 'src', 'main', 'resources')

    async def generate(self) -> tuple:
        """
        설정 파일 생성의 메인 진입점
        pom.xml과 application.properties 파일을 동시에 생성합니다.
        
        Returns:
            tuple: (pom_xml_content, properties_content)
        
        Raises:
            ConvertingError: 설정 파일 생성 중 오류 발생 시
        """
        logging.info("설정 파일 생성을 시작합니다.")
        
        try:
            # 템플릿 적용
            pom_content = POM_TEMPLATE.format(project_name=self.project_name)
            properties_content = PROPERTIES_TEMPLATE.format(project_name=self.project_name)
            
            # 파일 저장
            await save_file(pom_content, "pom.xml", self.project_path)
            await save_file(properties_content, "application.properties", self.resources_path)
            
            logging.info("설정 파일 생성이 완료되었습니다.\n")
            return pom_content, properties_content
        
        except Exception as e:
            logging.error(f"설정 파일 생성 중 오류: {str(e)}")
            raise ConvertingError(f"설정 파일 생성 중 오류: {str(e)}")
