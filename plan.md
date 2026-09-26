# OpsPilot — AI Production Incident Investigator

AI時代のフルスタックエンジニアとしての実力を証明するOSS。単なる「ChatGPTラッパー」ではなく、

> **AI × Web × Infrastructure × Database × Production Engineering**

を1つのリポジトリで証明する。

---

## 0. 結論(このドキュメントで最も重要な部分)

**最初に作るのはこれだけ。**

- CLI + **最小限のWeb UI**(read-only・単一ページ・認証なし)。MCP分割・複数MCPサーバー・フル機能Web UI(履歴保存/複数ユーザー等)は後回し
- 対象: **MariaDB slow query解析 + nginxログ解析 + 基本的なLinuxリソース確認**
- 診断は**read-only**(自動実行=Executeフェーズは実装しない。将来のロードマップに切り出す)
- LLMプロバイダは1つに絞る(コスト・実装単純化のため)
- ユーザーが**自分の本番環境を一切接続せずに**、`docker compose up` だけで動作を確認できる「壊れたデモ環境」を同梱する

Web UIを最小限とはいえv1に含める理由は、「フルスタックエンジニア」としてのアピールを最大化するため(詳細は§7)。ただしダッシュボードは調査結果を表示するだけの薄い層に限定し、認証・保存・複数ユーザー対応などは持たせず、スコープの肥大化を防ぐ。

以下、この結論に至った設計と、公開前に必ず潰しておくべき論点をまとめる。フルエコシステム構想(§6)は将来像であり、v1のスコープではない。

---

## 1. コンセプト

サーバー障害やWebアプリケーションの不具合をAIが調査するCLI。

```text
                    ┌───────────────┐
                    │    Engineer   │
                    └───────┬───────┘
                            │
                           CLI
                            │
                            ▼
                  ┌─────────────────┐
                  │    OpsPilot     │
                  │  Agent Engine   │
                  └────────┬────────┘
                           │
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
     nginx / app logs  MariaDB slow log   Linux resources
     (read-only)       + EXPLAIN          (CPU/Mem/Disk)
           │               │                │
           └───────────────┼────────────────┘
                           ▼
                   Root Cause Analysis
                    (evidence付き)
                           │
                           ▼
                 Suggested Remediation
                  (Executeはv1では行わない)
```

例:

```text
$ opspilot investigate

> Why is /api/search slow?

✓ Analyzing nginx access/error log
✓ Analyzing application log
✓ Analyzing MariaDB slow query log
✓ Running EXPLAIN
✓ Checking CPU / Memory / Disk

Root cause:

Finding #1
  slow.log: Query_time=18.241  Rows_examined=68496

Finding #2
  EXPLAIN: type=ALL key=NULL (full table scan)

Finding #3
  m_staff: missing composite index

Confidence: HIGH

Recommended index:
CREATE INDEX idx_staff_mall_disp
ON m_staff(m_staff_mall_id, m_staff_pc_disp);
```

ポイントは「原因はMariaDBだと思います」で終わらせず、ログ/EXPLAIN結果という**証拠(Evidence)付き**で回答すること。READMEにも

> OpsPilot never gives an infrastructure diagnosis without evidence.

と掲げる。これが最大の差別化軸。

処理フローは常に人間の承認を挟む(v1ではExecute自体を実装しないため、実質的にRecommendで止まる):

```text
Detect → Investigate → Explain → Recommend → (将来: Human Approval → Execute)
```

---

## 2. 機密情報の扱い(差別化ポイントとして明記)

nginxログ・アプリログ・SQLクエリには、パスワード・個人情報・内部IP・認証トークンなどが含まれ得る。これらを外部LLM APIに送信する前に、**必ずredaction(マスキング)を通す**。

- 送信前にログ/クエリ文字列から既知パターン(メールアドレス、トークンらしき文字列、`password=`等のクエリパラメータ、クレジットカード番号パターンなど)を検出し置換する処理を挟む
- redactionの挙動はテストで担保する(evalsとは別に、redactionの単体テストを用意する)
- READMEで「OpsPilot redacts secrets before sending to LLM」と明記し、Evidence-based AIと並ぶセールスポイントにする

「Evidence-based AI」を謳うOSSが同時に「送信前に機密情報を守る」設計を持つことは、単なるAgentフレームワークとの明確な差別化になる。

---

## 3. デモ環境(オンボーディングの核)

「5分でDockerで試せる」を実現する具体策として、**意図的に壊れたデモスタック**を同梱する。

```text
docker-compose.yml
├── mariadb-demo   (m_staffテーブル + 複合INDEX無し + わざと遅いクエリを打つseedスクリプト)
├── nginx-demo     (一部エンドポイントで502/timeoutを再現)
├── app-demo       (上記に対してリクエストを送る簡易アプリ)
├── opspilot-api   (FastAPI、analyzersをHTTP/SSEで公開)
└── opspilot-web   (Next.js、ダッシュボード。ビルド済みイメージとして同梱)
```

`docker compose up` 一発で「調査対象(壊れたデモスタック)」と「OpsPilot本体(api/web)」が両方立ち上がる構成にする。ダッシュボードをデモの主役に据える以上、Web UIもcompose対象に含めないと「5分で試せる」体験が成立しない。

ユーザー体験:

```bash
git clone <repo>
cd opspilot
docker compose up -d
# ブラウザで http://localhost:3000 を開き、"Investigate" を押す
# もしくは CLI から:
opspilot investigate --target demo
```

これにより、ユーザーは自分の本番環境やクレデンシャルを一切使わずに、OpsPilotの診断能力をその場で確認できる。

**LLM APIキーの扱い**: 決定論的な解析(slow log解析・EXPLAIN解析・redactionなど)はAPIキーなしで動作し、Finding一覧まではそのまま表示される。LLMによる自然言語の説明・Confidence判定は、`.env` にLLM APIキー(1プロバイダ分)を設定した場合のみ有効になる「モックモード」をデフォルトとする。これにより、APIキーを持たないユーザーでも `docker compose up` だけで解析結果そのものは確認でき、真の意味で「5分で試せる」を満たす。README/`.env.example` にこの2段階の挙動を明記する。

README冒頭には**Web UIの画面(進捗表示→レポート表示)を録画した10秒のデモGIF**を置く(CLI版のGIFはdocs/またはREADME内の折りたたみセクションに補足として残してもよいが、トップに置くのはWeb UI版で統一する)。

---

## 4. v1リポジトリ構成(最小)

フルエコシステム(§6)の構造をいきなり作らない。v1は以下で十分:

```text
opspilot/
├── README.md
├── LICENSE
├── cli/                  # CLI本体
├── api/                  # FastAPI: analyzersの結果をJSONで返す薄いAPI層 + SSEで進捗ストリーミング
├── web/                  # Next.js(TypeScript)製の単一ページダッシュボード(read-only)
├── analyzers/
│   ├── mysql.py          # slow log + EXPLAIN解析
│   ├── nginx.py          # access/error log解析
│   └── linux.py          # CPU/Mem/Disk確認
├── redact/               # 機密情報マスキング
├── demo/                 # docker-compose + seedスクリプト
├── tests/
└── docker-compose.yml
```

`cli/` と `web/` はどちらも `analyzers/` の同じロジックを呼ぶ構成にし、実装を重複させない(CLIはanalyzersを直接呼び、`api/`はanalyzersをHTTP/SSE越しに公開してWeb UIから使う)。`api/`が「✓ Analyzing nginx...」のような進捗をSSEでストリーミングし、Web UIがリアルタイム表示することで、CLIの体験をブラウザ上でも再現する。

### ライセンス

インフラを触るツールであるため意図的に選ぶ。基本方針: **MIT**(採用障壁を下げ、コントリビュータを集めやすくする)。将来的に特許条項が必要になった場合のみApache-2.0への変更を検討する。

---

## 5. マイルストーン(目安)

| 期間 | 内容 |
| --- | --- |
| Week 1-2 | analyzers/mysql.py + デモ環境(mariadb-demo) + CLI最小動作 |
| Week 3 | api/(FastAPI, SSEストリーミング) + web/ 最小ダッシュボード(Findings表示・進捗表示) |
| Week 4 | nginxログ解析 + Linuxリソース確認 + redaction実装 |
| Week 5 | README整備 + **Web UIのデモGIF撮影**(ターミナルではなくブラウザ画面を録画) + 英語README |
| Week 6+ | Evals実装 → **実測してから**結果を公開 → 反応を見てMCP分割/フル機能Web UI検討 |

Evalsのベンチマーク数値は、実装・実行前は一切README/docsに書かない。プレースホルダー数値を実績として公開しない。

---

## 6. Future Vision(v1完成後に検討する将来像)

以下はv1がユーザーに使われ、拡張する価値が確認できた場合の将来構想。**今は着手しない。**

### エコシステム化

```text
OpsPilot
├── opspilot-core
├── opspilot-mcp-linux
├── opspilot-mcp-mysql
├── opspilot-mcp-docker
├── opspilot-mcp-nginx
├── opspilot-evals
└── opspilot-web
```

### 最終形のリポジトリ構成

```text
opspilot/
├── README.md / LICENSE / CONTRIBUTING.md / SECURITY.md / CODE_OF_CONDUCT.md
├── apps/{api,web,cli}/
├── packages/{agent,tools,policies,evals}/
├── mcp/{linux,mysql,nginx,docker,git}/
├── evals/
├── examples/{nginx-502,mysql-slow-query,disk-full,docker-oom}/
├── docs/{architecture.md,security.md,benchmarks.md,agent-design.md}
├── docker/
└── .github/workflows/
```

注: ここでの `apps/web` は認証・複数ユーザー・調査履歴保存などを備えた**フル機能版**Web UIを指す。v1の `web/`(§4、単一ページ・認証なし・履歴保存なし)とは別物であり、v1のダッシュボードが評価された段階で `apps/web` へ発展させる想定。

### Evalsベンチマーク(実測後に公開する形式のイメージ)

```text
evals/
├── mysql/{missing-index.yaml, full-table-scan.yaml, lock-contention.yaml}
├── nginx/{upstream-timeout.yaml, 502-bad-gateway.yaml}
├── linux/{disk-full.yaml, high-load.yaml, oom.yaml}
└── docker/{restart-loop.yaml, memory-limit.yaml}
```

結果は実測後に「Incident Diagnosis Benchmark」として公開し、「AIを作れるだけでなく、AIを評価できる」ことを示す。

### Human Approval → Execute

デモ環境や十分なガードレール(Policy Engine + Risk Engine、`ALLOW/DENY/CONFIRM`判定)が整った段階で、実際にコマンド実行まで踏み込む。安全性設計は別途 `AgentShield`的な仕組みを内製 or 参照する。

### 他候補との関係

v1のMVPスコープは、検討した他候補のうち「DBDoctor AI」(MariaDB特化のAI Database Performance Investigator)にかなり近い。実装が進み、対象範囲がnginx/Linux/Docker/Gitへ広がった段階で自然に"OpsPilot"のブランドへ育てていく(GitHubリポジトリのrenameは後からでも容易なため、ブランド名の確定を急がない)。

### CodeContext MCP / LegacyLens

コードベース理解(AST解析 + 依存グラフ)やレガシーPHPのモダナイゼーション分析は、OpsPilotが軌道に乗った後の別OSS、または `opspilot-mcp-git` の拡張として検討する。

---

## 7. フルスタックとしての見せ方

CLIだけでは、GitHub閲覧者や採用担当者に「フルスタック」であることが一目で伝わりにくい。ターミナル出力より、動くWeb UI・デモGIFの方が技術力を瞬時に判断させやすいため、v1に最小Web UI(§4 `web/`)を組み込み、以下の4点を**1本のデモGIF**で同時に示す:

- **Frontend**: Next.js(TypeScript)によるリアルタイムUI(SSE受信、進捗の逐次表示、Findings/Evidence/Confidenceの可視化)
- **Backend**: FastAPIによる薄いAPI設計、`analyzers/`ロジックの再利用(CLIとWebで重複させない設計判断そのものもアピール材料)
- **Infrastructure**: Docker Compose、Linux/Nginx/MariaDBの実運用知識(デモ環境の構築)
- **AI**: Evidence-based diagnosis、送信前redaction、read-only安全設計

単なるAI APIラッパーとの違いは、これら4層が1つの一貫したプロダクトとして動作している点にある(README冒頭のデモGIFの扱いは§3参照)。

## 8. まとめ

上記4層(Frontend/Backend/Infrastructure/AI)が揃った時点で、リポジトリ1つで「AI APIを触れるだけでなく、実際のシステムを理解し、フロントエンドからインフラまで一気通貫で作れる」ことを、壮大な未完成の構想ではなく**動くもの**で示せる。個々の技術要素の一覧は§7を参照。
