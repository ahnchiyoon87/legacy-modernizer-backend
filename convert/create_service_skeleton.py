import os
import logging
import textwrap
from prompt.convert_variable_prompt import convert_variables
from prompt.convert_service_skeleton_prompt import convert_method_code
from prompt.convert_command_prompt import convert_command_code
from understand.neo4j_connection import Neo4jConnection
from util.exception import ConvertingError
from util.utility_tool import convert_to_camel_case, convert_to_pascal_case, save_file, build_java_base_path


# ----- Service Skeleton 생성 관리 클래스 -----
class ServiceSkeletonGenerator:
    """
    레거시 프로시저/함수를 분석하여 Spring Boot Service 스켈레톤을 자동 생성하는 클래스
    Neo4j에서 프로시저/함수 노드와 변수 정보를 조회하고,
    LLM을 활용하여 Service 클래스의 기본 구조와 메서드를 생성합니다.
    """

    def __init__(self, project_name: str, user_id: str, api_key: str, locale: str = 'ko'):
        """
        ServiceSkeletonGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
            api_key: LLM API 키
            locale: 언어 설정 (기본값: 'ko')
        """
        self.project_name = project_name
        self.user_id = user_id
        self.api_key = api_key
        self.locale = locale

    # ----- 공개 메서드 -----

    async def generate(self, entity_name_list: list, folder_name: str, file_name: str, 
                      global_variables: list) -> tuple:
        """
        Service Skeleton 생성의 메인 진입점
        Neo4j에서 프로시저/함수 정보를 조회하고, LLM 변환을 수행하여
        Service 클래스 스켈레톤과 Command 클래스 파일을 생성합니다.
        
        Args:
            entity_name_list: 서비스에서 사용할 엔티티 클래스명 목록
            folder_name: 폴더(시스템)명
            file_name: 파일명
            global_variables: 전역 변수 목록
        
        Returns:
            tuple: (method_info_list, service_skeleton, service_class_name, exist_command_class, command_class_list)
        
        Raises:
            ConvertingError: Service Skeleton 생성 중 오류 발생 시
        """
        logging.info("Service Skeleton 생성을 시작합니다.")
        connection = Neo4jConnection()
        
        # 속성 초기화
        self.folder_name = folder_name
        self.file_name = file_name
        object_name = os.path.splitext(file_name)[0]
        self.dir_name = convert_to_camel_case(object_name)
        self.service_class_name = convert_to_pascal_case(object_name) + "Service"

        try:
            # 프로시저 및 외부 호출 조회
            procedure_groups, self.external_packages = await self._fetch_procedures(connection)
            self.exist_command_class = any(g['parameters'] for g in procedure_groups.values())
            
            # 전역 변수 변환
            self.global_vars = convert_variables(global_variables, self.api_key, self.locale) if global_variables else {"variables": []}
            
            # 서비스 템플릿 생성
            service_skeleton = self._build_template(entity_name_list)

            # 프로시저별 메서드/커맨드 생성
            method_info_list = []
            command_class_list = []
            
            for proc_name, proc_data in procedure_groups.items():
                method_info = await self._process_procedure(proc_name, proc_data, service_skeleton)
                method_info_list.append(method_info)
                
                # Command 클래스 추가
                if (cmd_name := method_info.get('command_class_name')) and (cmd_code := method_info.get('command_class_code')):
                    command_class_list.append({'commandName': cmd_name, 'commandCode': cmd_code})
            
            logging.info(f"Service Skeleton 생성이 완료되었습니다: {self.service_class_name}\n")
            return method_info_list, service_skeleton, self.service_class_name, self.exist_command_class, command_class_list
        
        except ConvertingError:
            raise
        except Exception as e:
            logging.error(f"[{object_name}] Service Skeleton 생성 중 오류: {str(e)}")
            raise ConvertingError(f"[{object_name}] Service Skeleton 생성 중 오류: {str(e)}")
        finally:
            await connection.close()

    # ----- 내부 처리 메서드 -----

    async def _fetch_procedures(self, connection: Neo4jConnection) -> tuple:
        """
        프로시저/함수 노드 및 외부 호출 정보 조회
        
        Args:
            connection: Neo4j 연결 객체
        
        Returns:
            tuple: (procedure_groups, external_packages)
        """
        procedure_nodes, external_nodes = await connection.execute_queries([
            f"""MATCH (p {{folder_name: '{self.folder_name}', file_name: '{self.file_name}'}})
                WHERE p:PROCEDURE OR p:CREATE_PROCEDURE_BODY OR p:FUNCTION
                OPTIONAL MATCH (p)-[:PARENT_OF]->(d:DECLARE {{folder_name: '{self.folder_name}', file_name: '{self.file_name}'}})
                OPTIONAL MATCH (d)-[:SCOPE]-(dv:Variable {{folder_name: '{self.folder_name}', file_name: '{self.file_name}'}})
                OPTIONAL MATCH (p)-[:PARENT_OF]->(s:SPEC {{folder_name: '{self.folder_name}', file_name: '{self.file_name}'}})
                OPTIONAL MATCH (s)-[:SCOPE]-(sv:Variable {{folder_name: '{self.folder_name}', file_name: '{self.file_name}'}})
                WITH p, d, dv, s, sv, 
                    CASE WHEN p:FUNCTION THEN 'FUNCTION' WHEN p:PROCEDURE THEN 'PROCEDURE' ELSE 'CREATE_PROCEDURE_BODY' END as node_type
                RETURN p, d, dv, s, sv, node_type ORDER BY p.startLine""",
            f"""MATCH (p {{folder_name: '{self.folder_name}', file_name: '{self.file_name}'}})-[:CALL {{scope: 'external'}}]->(ext)
                WITH ext.object_name as obj_name, COLLECT(ext)[0] as ext
                RETURN ext"""
        ])
        
        # 프로시저 그룹 구성
        groups = {}
        for item in procedure_nodes:
            proc_name = item['p'].get('procedure_name', '')
            
            if proc_name not in groups:
                groups[proc_name] = {
                    'parameters': [],
                    'local_variables': [],
                    'param_keys': set(),
                    'var_keys': set(),
                    'declaration': (item.get('s') or {}).get('node_code', ''),
                    'node_type': item['node_type']
                }
            
            group = groups[proc_name]
            
            # 파라미터 추가
            if sv := item.get('sv'):
                sv_type, sv_name = sv['type'], sv['name']
                key = (sv_type, sv_name)
                if key not in group['param_keys']:
                    group['param_keys'].add(key)
                    group['parameters'].append({'type': sv_type, 'name': sv_name, 'parameter_type': sv.get('parameter_type', '')})
            
            # 로컬 변수 추가
            if dv := item.get('dv'):
                dv_type, dv_name, dv_value = dv['type'], dv['name'], dv['value']
                key = (dv_type, dv_name)
                if key not in group['var_keys']:
                    group['var_keys'].add(key)
                    group['local_variables'].append({'type': dv_type, 'name': dv_name, 'value': dv_value})
        
        # 임시 set 제거
        for g in groups.values():
            g.pop('param_keys', None)
            g.pop('var_keys', None)
        
        # 외부 패키지 추출
        external_packages = [ext['object_name'] for n in external_nodes if (ext := n.get('ext')) and ext.get('object_name')]
        
        return groups, external_packages

    def _build_template(self, entity_list: list) -> str:
        """
        Service 클래스 템플릿 생성
        
        Args:
            entity_list: 엔티티 목록
        
        Returns:
            str: Service 클래스 템플릿 코드
        """
        imports = []
        fields = []
        
        # Global variable fields
        if self.global_vars and (variables := self.global_vars.get("variables")):
            fields.extend(f"    private {v['javaType']} {v['javaName']} = {v['value']};" for v in variables)
        
        # Entity imports/fields
        if entity_list:
            project_prefix = f"com.example.{self.project_name}"
            for e in entity_list:
                entity_name = e['entityName']
                repo_name = f"{entity_name}Repository"
                imports.append(f"import {project_prefix}.entity.{entity_name};")
                imports.append(f"import {project_prefix}.repository.{repo_name};")
                fields.append(f"    @Autowired\n    private {repo_name} {entity_name[0].lower()}{entity_name[1:]}Repository;")
        
        # Command import
        if self.exist_command_class:
            imports.append(f"import com.example.{self.project_name}.command.{self.dir_name}.*;")
        
        # External service fields
        if self.external_packages:
            for p in self.external_packages:
                pascal, camel = convert_to_pascal_case(p), convert_to_camel_case(p)
                fields.append(f"    @Autowired\n    private {pascal}Service {camel}Service;")
        
        return f"""package com.example.{self.project_name}.service;

{chr(10).join(imports)}
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.beans.factory.annotation.Autowired;
import jakarta.persistence.EntityNotFoundException;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.beans.BeanUtils;
import java.time.format.DateTimeFormatter;
import org.springframework.stereotype.Service;
import java.time.temporal.TemporalAdjusters;
import java.time.*;
import java.util.*;

@Transactional
@Service
public class {self.service_class_name} {{
    {chr(10).join(fields)}

CodePlaceHolder
}}"""

    async def _process_procedure(self, proc_name: str, proc_data: dict, service_skeleton: str) -> dict:
        """
        프로시저별 메서드 및 Command 클래스 생성
        
        Args:
            proc_name: 프로시저명
            proc_data: 프로시저 정보
            service_skeleton: Service 스켈레톤 코드
        
        Returns:
            dict: 메서드 및 Command 정보
        """
        node_type = proc_data['node_type']
        parameters = proc_data['parameters']
        
        # Command 클래스 생성
        cmd_var = cmd_name = cmd_code = None
        if node_type != 'FUNCTION' and parameters:
            analysis_cmd = convert_command_code(
                {'parameters': parameters, 'procedure_name': proc_name},
                self.dir_name, self.api_key, self.project_name, self.locale
            )
            cmd_name, cmd_code, cmd_var = analysis_cmd['commandName'], analysis_cmd['command'], analysis_cmd['command_class_variable']
            
            # Command 파일 저장
            cmd_path = build_java_base_path(self.project_name, self.user_id, 'command', self.dir_name)
            await save_file(cmd_code, f"{cmd_name}.java", cmd_path)
        
        # Service 메서드 생성
        analysis_method = convert_method_code(
            {'procedure_name': proc_name, 'local_variables': proc_data['local_variables'], 'declaration': proc_data['declaration']},
            {'parameters': parameters, 'procedure_name': proc_name},
            self.api_key, self.locale
        )
        
        method_text, method_name, method_signature = analysis_method['method'], analysis_method['methodName'], analysis_method['methodSignature']
        method_code = textwrap.indent(method_text, '    ')
        
        return {
            'command_class_variable': cmd_var,
            'command_class_name': cmd_name,
            'method_skeleton_name': method_name,
            'method_skeleton_code': method_code,
            'method_signature': method_signature,
            'service_method_skeleton': service_skeleton.replace("CodePlaceHolder", method_code),
            'node_type': node_type,
            'procedure_name': proc_name,
            'command_class_code': cmd_code
        }
