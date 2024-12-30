import logging
import oracledb

from util.exception import ExecutePlsqlError, ExecuteSqlError

# DB 연결 정보
DB_CONFIG = {
    'user': 'c##debezium',
    'password': 'dbz',
    'dsn': 'localhost:1521/plsqldb'  
}

# 역할 : SQL 실행 함수
#
# 매개변수 : 
#   - sql_content : SQL 명령어 리스트
#
# 반환값 : 
#   - bool : SQL 실행 성공 여부
async def execute_sql(sql_content: list) -> bool:
    
    try:
        # * DB 연결
        connection = oracledb.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # * SQL 실행
        for statement in sql_content:
            if statement.strip():
                cursor.execute(statement)
                    
        connection.commit()
        return True
        
    except Exception as e:
        err_msg = f"SQL 실행 중 오류: {str(e)}"
        logging.error(err_msg)
        raise ExecuteSqlError(err_msg)
    finally:
        cursor.close()
        connection.close()


# 역할 : PLSQL 프로시저 실행 함수
#
# 매개변수 : 
#   - plsql_name : PLSQL 프로시저 이름
#   - params : PLSQL 프로시저 매개변수 딕셔너리
#
# 반환값 : 
#   - bool : PLSQL 프로시저 실행 성공 여부
async def execute_plsql(plsql_name: str, params: dict) -> bool:
    
    try:
        # * DB 연결
        connection = oracledb.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # * PLSQL 프로시저 실행
        cursor.callproc(plsql_name, keywordParameters=params)
        connection.commit()
        return True
        
    except Exception as e:
        err_msg = f"PLSQL 실행 중 오류: {str(e)}"
        logging.error(err_msg)
        raise ExecutePlsqlError(err_msg)
    finally:
        cursor.close()
        connection.close()