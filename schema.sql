-- 팀 편성 앱의 테이블. 이름은 모두 tf_ 로 시작한다.
-- 앱이 시작할 때 이 파일을 실행하므로 몇 번을 실행해도 같은 결과가 되게 쓴다(if not exists).

-- 학생과 관리자. 비밀번호는 bcrypt 해시로만 저장한다.
create table if not exists tf_students (
    id            serial primary key,
    student_no    text not null unique,
    name          text not null,
    main_role     text check (main_role in ('기획자', '웹 프로그래머', '프론트엔드 디자이너',
                                            '테스터', '보고서 작성자', '발표자')),
    password_hash text not null,
    is_admin      boolean not null default false
);

-- 보조 역할. 학생 1명에 0~2행.
create table if not exists tf_student_sub_roles (
    student_id integer not null references tf_students(id) on delete cascade,
    role       text not null check (role in ('기획자', '웹 프로그래머', '프론트엔드 디자이너',
                                             '테스터', '보고서 작성자', '발표자')),
    primary key (student_id, role)
);

-- 팀. id 가 팀 번호(1, 2, …)이며 화면의 team_1, apply_1 의 번호와 같다.
create table if not exists tf_teams (
    id   integer primary key,
    name text not null unique
);

-- 팀원. (team_id, slot_no) 기본 키와 student_id 유일성 제약이
-- "마지막 자리에 두 명이 동시에 들어감"(먼저 도착한 학생만 기록)과 "한 학생은 한 팀에만 소속"을 DB에서 지킨다.
create table if not exists tf_members (
    team_id    integer not null references tf_teams(id) on delete cascade,
    slot_no    integer not null check (slot_no between 1 and 4),
    student_id integer not null unique references tf_students(id) on delete cascade,
    primary key (team_id, slot_no)
);

-- 지원.
create table if not exists tf_applications (
    id         serial primary key,
    team_id    integer not null references tf_teams(id) on delete cascade,
    student_id integer not null references tf_students(id) on delete cascade,
    status     text not null check (status in ('대기', '승인', '거절')),
    reason     text,
    created_at timestamptz not null default now(),
    decided_at timestamptz
);

-- 한 학생은 결과를 기다리는 지원을 1개만 가질 수 있다.
create unique index if not exists tf_applications_one_pending
    on tf_applications (student_id) where status = '대기';

-- 투표. 한 팀원은 한 지원에 한 번만 투표한다.
create table if not exists tf_votes (
    application_id integer not null references tf_applications(id) on delete cascade,
    voter_id       integer not null references tf_students(id) on delete cascade,
    vote           text not null check (vote in ('찬성', '거부')),
    created_at     timestamptz not null default now(),
    primary key (application_id, voter_id)
);

-- 설정. 예: closed = 'true' / 'false' (모집 마감 여부)
create table if not exists tf_settings (
    key   text primary key,
    value text not null
);

-- AI 호출 기록. 모델마다 결과(성공, 시간 초과, 빈 응답, 오류, 검사 불합격)를 남긴다.
create table if not exists tf_ai_logs (
    id          serial primary key,
    created_at  timestamptz not null default now(),
    attempt     integer not null,
    model       text not null,
    outcome     text not null,
    detail      text,
    elapsed_sec real
);
