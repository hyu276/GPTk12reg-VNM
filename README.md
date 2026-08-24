# chatgpt-register-k12

`chatgpt-register-k12` là công cụ WebUI chạy cục bộ để quản lý nhóm hộp thư, đăng ký hoặc đăng nhập tài khoản ChatGPT, làm mới ngữ cảnh Không gian làm việc (Workspace) của tài khoản và xuất nhiều định dạng JSON tương thích. Mặc định công cụ xuất Sub2API; bạn cũng có thể chuyển sang auth.json, CPA, Cockpit, 9router, AxonHub và các định dạng khác.

Dự án hỗ trợ nhóm hộp thư Outlook/Gmail OAuth, bí danh Outlook dạng plus alias, kiểm tra ngữ cảnh Workspace/K12, đăng nhập tài khoản hiện có bằng mã xác minh gửi qua email, chạy đồng thời và lưu trữ kết quả theo từng lần chạy. Mọi cấu hình trong repository đều là ví dụ đã ẩn thông tin nhạy cảm, không chứa email, mật khẩu, token, Workspace ID hay kết quả chạy thực tế.

> Chỉ sử dụng công cụ với hộp thư, tài khoản và Không gian làm việc mà bạn có quyền sử dụng; đồng thời tự kiểm tra Điều khoản dịch vụ và các yêu cầu tuân thủ có liên quan.

## Tính năng

- Hỗ trợ nhóm hộp thư Outlook OAuth để nhận mã xác minh
- Hỗ trợ nhóm hộp thư Gmail OAuth/IMAP/Mật khẩu ứng dụng để nhận mã xác minh
- Hỗ trợ mở rộng địa chỉ Outlook bằng bí danh `+số`
- Hỗ trợ toàn bộ quy trình: đăng ký, tham gia/gửi yêu cầu vào Workspace, refresh/check và xuất dữ liệu
- Hỗ trợ hai luồng chính trong WebUI cục bộ
- Hỗ trợ đăng nhập tài khoản hiện có bằng mã xác minh email và lấy lại token
- Hỗ trợ nhận diện ngữ cảnh K12/Workspace, tránh xuất nhầm ngữ cảnh Personal/Free chưa được xác nhận
- Chống trùng lặp theo `workspace_id + email`; cùng một email có thể được dùng cho nhiều Workspace khác nhau
- Có thể cấu hình chạy song song cho các giai đoạn đăng ký, tham gia Workspace và làm mới
- Tự động lưu kết quả theo thời gian chạy và số lượng tài khoản
- Hỗ trợ nhiều định dạng JSON; mặc định là Sub2API

## Quy trình hoạt động

```text
Nhóm hộp thư -> Đăng ký tài khoản mới hoặc đăng nhập tài khoản hiện có bằng mã xác minh -> Tham gia/gửi yêu cầu vào Workspace -> Refresh/check ngữ cảnh tài khoản -> Kiểm tra tình trạng hoạt động -> Xuất JSON
```

Sau một lần chạy đầy đủ, mặc định một thư mục riêng sẽ được tạo trong `runs/`:

```text
runs/
  20260706-093012_6_accounts/
    registered_accounts.json
    sub2api_bundle.json
    test_run.log
```

Các tệp trạng thái dùng chung giữa nhiều lần chạy được lưu tại:

```text
data/outlook_token_state.json
data/workspace_account_state.json
```

`outlook_token_state.json` ghi nhận thông tin xác thực của hộp thư có bị mất hiệu lực hay đang được tạm sử dụng hay không. `workspace_account_state.json` ghi trạng thái đã xử lý, kiểm tra hoặc xuất theo `workspace_id + email`. Việc một email đã được xuất vào Workspace A không ngăn email đó tiếp tục được dùng với Workspace B.

## Cài đặt

```bash
git clone <this-repo>
cd chatgpt-register-k12
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell:

```powershell
git clone <this-repo>
cd chatgpt-register-k12
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Phụ thuộc:

- `curl-cffi`
- `pyyaml`

## Bắt đầu nhanh: WebUI cục bộ

Tạo tệp cấu hình cục bộ:

```bash
chatgpt-register init
```

Khởi động WebUI:

```bash
chatgpt-register web -c config.yaml --host 127.0.0.1 --port 8787
```

Mở địa chỉ:

```text
http://127.0.0.1:8787/
```

Trong trang WebUI, bạn có thể nhập hoặc lưu:

- Nhóm hộp thư
- Proxy
- Workspace ID
- Định dạng xuất
- Số lượng và số luồng xử lý
- Loại hộp thư: Outlook Token / Gmail App Password
- Thiết lập bí danh email

Trang có hai nút luồng chính:

```text
Đăng ký khi chưa có tài khoản
Đăng nhập tài khoản hiện có để lấy token mới
```

`Đăng ký khi chưa có tài khoản` sẽ lần lượt thực hiện đăng ký, join, refresh/check và xuất dữ liệu. `Đăng nhập tài khoản hiện có để lấy token mới` trước tiên sẽ thử đăng nhập bằng mã xác minh gửi qua email; nếu OpenAI yêu cầu mật khẩu, công cụ sẽ tự động dùng mật khẩu cố định tích hợp trong dự án `#A1234567890` để đăng nhập và lấy lại token, sau đó tiếp tục join, refresh/check và xuất dữ liệu. Định dạng mặc định là Sub2API và có thể đổi trong danh sách thả xuống “Định dạng xuất”.

Tài khoản mới đăng ký sẽ sử dụng mật khẩu cố định tích hợp trong dự án `#A1234567890`, giúp có thể đăng nhập lại bằng mật khẩu để lấy token về sau. Thiết lập này không thay đổi mật khẩu của các tài khoản đã được đăng ký trước đó.

Tệp đầu ra được lưu trong:

```text
runs/YYYYMMDD-HHMMSS_<count>_accounts/
```

## Sử dụng bằng dòng lệnh

CLI cũ vẫn hoạt động. Để chạy toàn bộ quy trình:

```bash
chatgpt-register run -c config.yaml -n 6 -t 3 --workspace-id <workspace-uuid> -v
```

Ý nghĩa tham số:

- `-n 6`: đăng ký 6 tài khoản trong lần chạy này
- `-t 3`: mỗi giai đoạn sử dụng tối đa 3 worker
- `--workspace-id`: UUID của Workspace đích
- `-v`: hiển thị nhật ký chi tiết

## Ví dụ tối thiểu: dùng 1 hộp thư Outlook để đăng ký 6 tài khoản

Outlook hỗ trợ plus alias. Khi bật bí danh, một hộp thư chính có thể lần lượt được dùng với các địa chỉ:

```text
user@example.com
user+1@example.com
user+2@example.com
user+3@example.com
user+4@example.com
user+5@example.com
```

Ví dụ cấu hình:

```yaml
mail:
  providers:
    - type: outlook_token
      enable: true
      mode: auto
      alias_enabled: true
      alias_limit_per_mailbox: 5
      alias_custom_name_enabled: false
      alias_custom_names: |
        alpha
        beta
      mailboxes: |
        user@example.com----mail_password----client_id----refresh_token

proxy:
  url: "socks5://127.0.0.1:10808"

workspace:
  enabled: true
  ids:
    - "your-workspace-uuid"
  route: k12_request
  re_login_enabled: false
```

Chạy:

```bash
chatgpt-register run -c config.yaml -n 5 -t 3 --workspace-id <workspace-uuid> -v
```

Tệp kết quả nằm tại:

```text
runs/YYYYMMDD-HHMMSS_5_accounts/sub2api_bundle.json
```

## Định dạng xuất

Định dạng mặc định là `sub2api`. Các định dạng được hỗ trợ:

- `sub2api`: bundle Sub2API, tên tệp mặc định `sub2api_bundle.json`
- `auth`: kiểu Codex/ChatGPT auth.json, tên tệp mặc định `auth.json`
- `raw-session`: kiểu Session JSON, tên tệp mặc định `session.json`
- `cpa`: mảng tài khoản kiểu CPA, tên tệp mặc định `cpa.json`
- `cockpit`: mảng tài khoản kiểu Cockpit, tên tệp mặc định `cockpit.json`
- `9router`: mảng tài khoản kiểu 9router, tên tệp mặc định `9router.json`
- `axonhub`: mảng tài khoản kiểu AxonHub, tên tệp mặc định `axonhub-auth.json`

Có thể cố định định dạng xuất trong tệp cấu hình:

```yaml
export:
  format: sub2api
  output_file: ""
```

Khi `output_file` để trống, chương trình tự chọn tên tệp mặc định theo định dạng. Để tương thích với cấu hình cũ, `sub2api.output_file` vẫn có hiệu lực với định dạng Sub2API.

Tạm đổi định dạng bằng CLI:

```bash
chatgpt-register run -c config.yaml -n 5 -t 3 --workspace-id <workspace-uuid> --format cpa -v
chatgpt-register export -c config.yaml -i registered_accounts.json --format 9router -v
```

## Cấu hình

Xem ví dụ đầy đủ trong `config.example.yaml`. Dưới đây là các mục cấu hình chính.

### Nhóm hộp thư

Định dạng nhóm Outlook token:

```text
email----password----client_id----refresh_token
```

Định dạng nhóm Gmail OAuth:

```text
email----client_id----client_secret----refresh_token
```

Định dạng nhóm Gmail App Password:

```text
email@gmail.com----16-character-App-Password
```

Có thể giữ nguyên khoảng trắng trong App Password; chương trình sẽ tự loại bỏ. Trước khi dùng Gmail App Password, tài khoản Gmail cần bật Xác minh 2 bước, đã tạo Mật khẩu ứng dụng và cho phép truy cập IMAP. Trong WebUI, chọn `Gmail App Password` rồi nhập theo định dạng trên.

### Bí danh email

```yaml
alias_enabled: true
alias_limit_per_mailbox: 5
alias_custom_name_enabled: false
alias_custom_names: |
  alpha
  beta
```

Ý nghĩa:

- `alias_enabled`: có bật plus alias hay không
- `alias_limit_per_mailbox`: số địa chỉ đăng ký tối đa cho mỗi hộp thư chính, tính cả địa chỉ chính; chương trình giới hạn từ 1 đến 6
- `alias_custom_name_enabled`: có bật tên plus alias tùy chỉnh hay không
- `alias_custom_names`: tag tùy chỉnh, mỗi dòng một tag; ví dụ `alpha` tạo `user+alpha@example.com`

Mã xác minh vẫn được đọc từ hộp thư chính; địa chỉ dùng để đăng ký được phân biệt theo từng bí danh cụ thể. Outlook Token và Gmail App Password đều hỗ trợ plus alias như `user+1@example.com`.

Khuyến nghị mặc định là dùng 5 địa chỉ cho mỗi hộp thư chính (địa chỉ chính + `+1` đến `+4`). Nếu bật tên tùy chỉnh, hộp thư chính vẫn chiếm vị trí đầu tiên; tag tùy chỉnh được ưu tiên, nếu chưa đủ chương trình tiếp tục dùng `+1`, `+2` để bổ sung. Giới hạn cứng là 6 địa chỉ.

### Workspace

```yaml
workspace:
  enabled: true
  ids:
    - "your-workspace-uuid"
  route: k12_request
  re_login_enabled: false
  export_plan_type: k12
```

Các route thường dùng:

- `accept`
- `request`
- `k12_request`

Mặc định nên dùng refresh/check để xác nhận ngữ cảnh Workspace hiện tại của tài khoản trước khi xuất JSON Sub2API.

### Kiểm tra tình trạng trước khi xuất

```yaml
sub2api:
  require_team_tokens: auto
  health_check: true
  health_check_endpoint: check
  health_check_retries: 2
  health_check_delay_seconds: 5
```

Khi bật `health_check`, trước khi xuất chương trình thực hiện một kiểm tra nhẹ qua ChatGPT backend. Chế độ `check` mặc định ưu tiên xác nhận tài khoản vẫn ở đúng ngữ cảnh K12/Workspace. Tài khoản đã bị phía dịch vụ thu hồi, trả về `token_revoked` / `token_invalidated`, hoặc gặp lỗi tại API kiểm tra sẽ không được ghi vào JSON xuất cuối cùng. Vì vậy số lượng tài khoản được xuất có thể ít hơn số lượng đăng ký thành công; mục đích là tránh trường hợp vừa nhập dữ liệu đã gặp lỗi 401.

### Lưu trữ đầu ra

```yaml
output:
  archive_runs: true
  runs_dir: runs
```

Khi bật, lệnh `run` đầy đủ sẽ ghi kết quả của từng lần chạy vào một thư mục riêng để tránh làm đầy thư mục gốc.

## Lệnh

| Lệnh | Mô tả |
| --- | --- |
| `web` | Khởi động WebUI cục bộ |
| `init` | Tạo `config.yaml` mặc định |
| `register` | Chỉ thực hiện đăng ký |
| `join-workspace` | Tham gia/gửi yêu cầu vào Workspace cho tài khoản hiện có |
| `refresh` | Làm mới token và kiểm tra ngữ cảnh tài khoản/Workspace |
| `login-team` | Luồng đăng nhập lại Team/Workspace mang tính thử nghiệm |
| `export` | Xuất bản ghi tài khoản hiện có sang định dạng JSON được chọn |
| `run` | Toàn bộ quy trình: register -> join -> refresh/check -> export |

Ví dụ:

```bash
chatgpt-register web -c config.yaml --host 127.0.0.1 --port 8787
chatgpt-register register -c config.yaml -n 5 -t 3 -v
chatgpt-register join-workspace -c config.yaml -i registered_accounts.json --workspace-id <workspace-uuid> -t 5 -v
chatgpt-register refresh -c config.yaml -i registered_accounts.json --workspace-id <workspace-uuid> -t 5 -v
chatgpt-register export -c config.yaml -i registered_accounts.json -o sub2api_bundle.json -v
chatgpt-register export -c config.yaml -i registered_accounts.json --format cpa -v
```

## Dùng lại tài khoản hiện có với Workspace khác

Tệp trạng thái hộp thư chỉ ảnh hưởng đến việc “một hộp thư/bí danh còn có thể được dùng để đăng ký tài khoản mới hay không”; nó không ngăn tài khoản đã đăng ký tiếp tục tham gia Workspace khác.

Khi dùng lại tài khoản hiện có, không cần đăng ký lại. Chỉ cần sử dụng `registered_accounts.json` hiện có:

```bash
chatgpt-register join-workspace -c config.yaml -i registered_accounts.json --workspace-id <new-workspace-uuid> -t 5 -v
chatgpt-register refresh -c config.yaml -i registered_accounts.json --workspace-id <new-workspace-uuid> -t 5 -v
chatgpt-register export -c config.yaml -i registered_accounts.json -o sub2api_bundle.json -v
```

## Tệp đầu ra

Các tệp đầu ra thường gặp:

- `registered_accounts.json`: bản ghi các tài khoản đăng ký thành công
- `sub2api_bundle.json` / `cpa.json` / `9router.json`, v.v.: JSON xuất cuối cùng
- `test_run.log`: nhật ký chạy
- `data/outlook_token_state.json`: trạng thái hộp thư/bí danh

Theo mặc định, khi chạy `run` đầy đủ, ba tệp đầu tiên sẽ nằm trong `runs/YYYYMMDD-HHMMSS_<count>_accounts/`.

## Lưu ý

- Chỉ sử dụng hộp thư, tài khoản và Workspace mà bạn có quyền truy cập.
- Không nên đặt mức chạy đồng thời quá cao vì có thể kích hoạt giới hạn của dịch vụ email hoặc dịch vụ đích.
- `login-team` vẫn là luồng thử nghiệm; quy trình mặc định dùng refresh/check để lấy ngữ cảnh Không gian làm việc.
- `require_team_tokens: auto` sẽ tuân theo `workspace.re_login_enabled`.

## Ghi nhận

Cảm ơn cộng đồng [LINUX DO](https://linux.do/) đã trao đổi và hỗ trợ.
