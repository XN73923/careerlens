# CareerLens Portfolio Presentation

この文書は、CareerLensを採用担当者・面接官へ短時間で説明するための補助資料です。READMEでは製品全体を、ここでは「なぜ作ったか」「どこに技術的な工夫があるか」「どうデモするか」を説明します。

## 30秒で説明する

> CareerLensは、就職活動の企業研究と選考準備を一つの流れで管理する、Python・Streamlit製のローカルファーストアプリです。企業メモだけでなく、参照したURLと取得時点の本文をSnapshotとして保存します。AIにはユーザーが選んだ本文だけを渡し、根拠がない内容は情報不足として扱います。AI結果も自動反映せず、ユーザーが確認して採用する設計にしました。

## このProjectで示したいこと

### Product / DX Perspective

- 「AIを入れること」ではなく、企業研究の分散・再確認・選考準備というworkflow上の課題から設計した
- 情報収集、根拠管理、AI整理、ユーザー判断を一つのflowにつないだ
- MVPの範囲を限定し、不要なscore、自動推薦、完成回答生成を入れなかった
- 利用者が結果を検証し、採用・不採用を制御できるHuman-in-the-loopを重視した

### Engineering Perspective

- StreamlitとSQLiteで小さく開始し、責務が生じた段階でmoduleを分離した
- source metadataとretrieved source textを別tableで管理した
- SSRFを意識したURL / DNS / redirect検証とresponse制限を実装した
- strict JSON Schemaに加え、ID・所有関係・根拠抜粋をapplication側でも検証した
- temporary DB、mock HTTP、fake AI client、Streamlit AppTestで回帰テストした

## 3分Demo Flow

実APIの速度やcreditに依存しないよう、基本は保存済みデータとAI履歴を使って説明します。

### 0:00–0:25 — Home

見せるもの：

- 4-step workflow
- Source-aware / AI-assisted / Local-first

説明例：

> 企業研究から選考準備までを分断せず、自分の情報、企業情報、根拠、AI整理を順番につなぐ製品です。AIは判断者ではなく、研究を整理する補助役として設計しています。

### 0:25–0:50 — My Profile

見せるもの：

- 志望職種
- 並べ替え可能な就活軸
- 独立した経験・エピソードとtags

説明例：

> 就活軸は固定scoreではなく、現在の優先順としてユーザーが管理します。経験も一つの長文ではなく、後で選択できるcollectionとして保存します。

### 0:50–1:25 — Company Research

見せるもの：

- 複数企業の切り替え
- USER-ENTERED company research
- SOURCE METADATA
- 本文取得済みstatus、取得日時、Snapshot履歴

説明例：

> 企業情報とSourceを分けています。URLを保存しただけでは本文確認済みと扱いません。「本文を取得」を押した時だけ公開ページを取得し、再取得時も過去Snapshotを残します。

### 1:25–2:05 — Research Assistant

見せるもの：

- 使用するSnapshotの明示的なcheckbox
- RETRIEVED EVIDENCE
- EVIDENCE-BACKED resultの根拠抜粋
- 情報不足、追加調査質問、制約
- 「採用」「編集して採用」「採用しない」

説明例：

> AIは選択された本文だけを事実根拠として使います。返却された抜粋が本当にSnapshot内に存在するかを検証し、根拠不足の項目は補完させません。AI結果は自動上書きせず、フィールド単位でユーザーが採用します。

### 2:05–2:45 — Selection Preparation

見せるもの：

- 企業情報 × 就活軸 × 経験
- 使用する就活軸と経験の選択
- 企業側の根拠とAIによる接点整理
- 選考準備材料、逆質問候補、追加調査項目

説明例：

> 企業との相性を点数化するのではなく、ユーザーが選んだ就活軸と経験について、話す材料と不足情報を整理します。出力は完成回答ではなく、ユーザーが考えるための材料です。

### 2:45–3:00 — Architecture / Closing

説明例：

> 技術構成はPython、Streamlit、SQLite、OpenAI Responses APIです。MVPでは複雑なframeworkを避けましたが、DB、retrieval、AI validationを分離し、外部通信部分はmock可能にしています。

## Live Demo Checklist

デモ前：

- `.env`とAPI keyが画面・terminal・Git差分に出ていないことを確認
- サンプルプロフィール、企業、Source、Snapshot、AI履歴を準備
- `python -m pytest -q`が成功することを確認
- 画面幅を13–14 inch laptop相当にし、sidebarを開く
- 実行時のnetwork依存を避ける場合は、本文取得・AI実行を押さず履歴を見せる

デモ中：

- 個人情報を含む自由メモや経験詳細を不用意に表示しない
- `EVIDENCE-BACKED`は「正解保証」ではなく「根拠追跡可能」の意味だと説明
- AIの採用buttonを押す場合、既存データを変える操作であることを先に説明
- 削除確認、API実行、本文再取得を誤操作しない

## Key Design Decisions

| Decision | Reason | Trade-off |
|---|---|---|
| Local-first SQLite | 個人の就活情報を小さく扱い、setupを簡単にする | 複数端末・複数user同期はできない |
| Streamlit multipage | Python中心でworkflow検証とUI構築を早く行う | frontendの細かなstate制御には限界がある |
| Sourceと本文を分離 | URL保存と内容確認を混同しない | tableとUI状態が1段増える |
| RetrievalごとにSnapshot | 取得時点とAI根拠を後から追える | local DB sizeが増える |
| Explicit evidence selection | AIへ送る情報と根拠をユーザーが把握できる | 完全自動より操作が増える |
| Strict structured output | UI表示とvalidationを安定させる | schema変更時にversion管理が必要 |
| Controlled Adoption | AIがユーザー記録を勝手に変更しない | 確認操作が増える |
| No fit score | 根拠の薄い数値でcareer判断を誘導しない | 一覧比較の即時性は下がる |

## Development Story

Git履歴は、次の順序でMVPを積み上げています。

1. Product Requirementsと最小data model
2. Streamlit shellとSQLite initialization
3. Basic Profile
4. Job Axes CRUD / ordering
5. Experiences CRUD
6. Company Research CRUD
7. Source Management
8. AI Research Assistant
9. Webpage Retrieval
10. Evidence Snapshot persistence
11. Evidence-backed AI Research
12. Controlled AI Adoption
13. Selection Preparation
14. Final UI / Navigation Polish

外部APIの前にlocal CRUDを完成させ、AI導入後もretrieval、evidence、adoptionを別Milestoneとして追加しました。機能を一度に広げず、failure modeごとにtestとUI確認を追加した点が開発プロセス上の特徴です。

## Interview Q&A

### なぜAIにWeb検索を任せなかったのですか？

AIが何を読んだか不明になるためです。v0.1では、Source登録、本文取得、Snapshot選択を明示的な別工程にし、AI入力を確認可能にしました。

### Evidence-backedなら結果は正しいですか？

正しさを保証しません。選択したSnapshotと抜粋へ戻れること、根拠外の主張を検出しやすいことが目的です。Source自体の正確性や最新性はユーザーが確認します。

### なぜVector DatabaseやRAG frameworkを使わなかったのですか？

v0.1の対象は、ユーザーが少数のSourceとSnapshotを明示的に選ぶworkflowです。現時点ではSQLiteと文字数制限で十分であり、検索規模が必要になる前に複雑性を追加しない判断です。

### なぜAI結果をCompany Researchへ自動反映しないのですか？

企業情報は後続の選考準備にも使われるため、誤った内容の自動混入を避ける必要があります。比較、編集、置換確認を含むuser-controlled adoptionにしています。

### Source Retrievalの安全性はどう考えましたか？

URL scheme、hostname、解決IP、redirect先を検証し、private networkへのアクセスを拒否します。また、timeout、response size、content type、redirect回数を制限しています。

### 次に改善するなら何ですか？

まずPDF / IR資料の安全な取得と、Latest News検索をSource workflowへ統合します。その後、実利用から必要性が確認できれば比較・report出力・deploymentを検討します。

## Honest Limitations

- 本文取得はstatic HTML / plain textのみ
- PDF、JavaScript-rendered content、Latest News検索は未対応
- AI利用にはOpenAI API keyとcreditが必要
- local single-userで、authentication・cloud syncはない
- SourceとAI結果の正確性・最新性は保証しない
- 実ユーザー調査やproduction運用を完了した製品ではなく、portfolio MVPである

この制約を隠さず、今後の拡張候補とv0.1で意図的に実装しなかった項目を区別して説明します。
