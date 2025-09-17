import os


# ===== 사용자가 여기 값을 수정하면 됩니다 =====
BASE_DIR = r"D:\다운로드\HDAPS 프로시저 모음"  # 합산할 최상위 폴더 경로
# ============================================


def iter_files(root_dir: str):
    for current_dir, _subdirs, files in os.walk(root_dir):
        for file_name in files:
            yield os.path.join(current_dir, file_name)


def main() -> int:
    base_dir = os.path.abspath(BASE_DIR)
    if not os.path.isdir(base_dir):
        print(f"[오류] 폴더가 아닙니다: {base_dir}")
        return 2

    print(f"[합산 시작] dir='{base_dir}', 확장자: .sql, .txt")

    total_bytes = 0
    file_count = 0

    for path in iter_files(base_dir):
        name_lower = os.path.basename(path).lower()
        if not (name_lower.endswith('.sql') or name_lower.endswith('.txt')):
            continue
        try:
            total_bytes += os.path.getsize(path)
            file_count += 1
        except Exception as exc:  # pragma: no cover
            print(f"[경고] 크기를 읽지 못했습니다: {path} ({exc})")
            continue

    total_kb = total_bytes / 1024.0
    print(f"[요약] 대상 파일 {file_count}개, 총 {total_kb:.2f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


