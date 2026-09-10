# CareerLens — Product Requirements

## 1. Overview

**CareerLens** は、就職活動における企業研究と選考準備を効率化するためのAI支援ツールである。

企業研究では、企業Webサイト、採用サイト、IR資料、ニュースなど複数の情報源を確認する必要があり、情報収集と整理に多くの時間がかかる。

また、企業について理解した後も、その情報を自分自身の就活軸や経験と結び付け、志望理由や面接で確認したい内容へ整理する必要がある。

CareerLensでは、公開情報の整理とAIによる分析支援を通じて、この一連の企業研究プロセスを効率化することを目指す。

---

## 2. Product Concept

> **AIが企業研究やキャリア選択を代行するのではなく、情報整理と考察を支援し、最終的な判断はユーザー自身が行う。**

CareerLensでは、ユーザーが入力・保存した情報とAIが生成した情報を明確に区別する。また、可能な限り根拠となる情報源を表示し、ユーザー自身が内容を確認できる設計を重視する。

AIは与えられた情報から判断できない内容を推測で補わず、「情報不足」または追加確認が必要な項目として提示する。

---

## 3. Target User

主な対象ユーザーは、企業研究や面接準備を行う就職活動中の学生である。

特に以下のような課題を持つユーザーを想定する。

* 複数のWebサイトや資料を確認するため、企業研究に時間がかかる
* 調べた情報が分散し、後から整理しにくい
* 企業の特徴と自分の就活軸や経験との接点を整理することが難しい
* 志望動機や面接質問を考える前段階の情報整理に時間がかかる

---

## 4. v0.1 Scope and Assumptions

v0.1は、個人がローカル環境で利用するシングルユーザー向けアプリケーションとして開発する。

* UIは4つのStreamlitページで構成する
* データはローカルのSQLiteデータベースに保存する
* ユーザー認証は実装しない
* 企業情報はユーザーが管理する。取得済みEvidenceに基づくAI提案は自動反映せず、ユーザーがフィールド単位で確認・採用した場合のみ変更する
* AI処理はユーザーが明示的に実行した場合のみ行う
* v0.1のLLM APIにはOpenAI Responses APIを使用する
* 公開Webページの本文取得は、ユーザーが指定したURLへの明示的な操作に限定する
* Latest Newsおよびニュース・検索API連携はv0.1には含めない

---

## 5. Core User Flow

```text
My Profileを設定
  ├─ 志望職種・自由メモ
  ├─ 複数の就活軸
  └─ 複数の経験・エピソード
        ↓
企業を登録
        ↓
企業情報と情報源を収集・整理し、必要なWeb本文をSnapshotとして保存
        ↓
選択した取得済み本文を根拠にAIで企業研究を整理
        ↓
企業情報 × 就活軸 × 経験の接点を整理
        ↓
選考準備
```

---

## 6. MVP Pages and Features

### 6.1 My Profile

ユーザー自身の基本情報、就活軸、経験・エピソードを管理する。

#### A. Basic Profile

最小限のプロフィール情報として、以下を登録・編集できる。

* 志望職種
* 自由メモ

#### B. Job-search Criteria（就活軸）

ユーザーが企業選びで重視する観点を複数登録できる。

例：

* DX・ITを通じた現場課題の解決
* 上流工程への関与
* 幅広い事業領域
* AI・デジタル技術への積極性
* グローバルな事業環境

各就活軸は以下の情報を持つ。

* 就活軸の内容
* 任意の説明
* 表示順

ユーザーは就活軸を追加・編集・削除・並べ替えできる。就活軸は固定せず、就職活動の進行に合わせて更新できるようにする。

#### C. Personal Experiences / Episodes

学生団体、インターン、ボランティア、学業など、選考準備で活用する可能性がある経験・エピソードを複数登録できる。経験は1つの自由記述欄にまとめず、独立したコレクションとして管理する。

各経験は以下の情報を持つ。

* タイトル
* カテゴリ
* 短い要約
* 詳細
* 任意のスキル・タグ

ユーザーは経験を追加・編集・削除し、保存済みの複数の経験を一覧・詳細表示できる。

AIは、企業の特徴や特定の面接テーマに関連しそうな経験を候補として提示できる。ただし、どの経験を実際に使用するかはユーザー自身が最終判断する。

---

### 6.2 Company Research

研究対象となる企業を登録し、企業研究情報を一か所に整理する。

主な企業情報：

* 企業名
* 主な事業
* 強み・特徴
* 経営戦略
* DX・AI関連施策
* 海外事業
* 採用職種・仕事内容
* 自由メモ

各企業には、根拠や追加確認に利用できる情報源を複数登録する。

主な情報源の項目：

* タイトル
* URL
* 種別（企業サイト、採用サイト、IR、ニュース、その他など）
* 公開日（任意）
* メモ

企業情報と情報源はユーザーが追加・編集・削除できる。取得済みEvidenceに基づくAI提案はCompany Researchへ自動では書き戻さず、ユーザーが内容と根拠を確認し、フィールド単位で明示的に採用した場合のみ反映する。

v0.1では、ユーザーが指定した公開URLのHTMLまたはplain text本文だけを明示的に取得し、取得時点のSnapshotとして保存する。リンク先の自動巡回やJavaScript renderingを行うWebクローラーは実装しない。

---

### 6.3 Research Assistant

保存済みの企業情報と、ユーザーが明示的に選択した取得済み本文をもとに、AIが企業研究の整理を支援する。

#### AI-assisted Research

主な支援内容：

* 保存済み企業情報の整理
* 企業の重要な特徴の抽出
* DX・AI関連施策の整理
* 今後注目すべき事業領域の提示
* 情報が不足している項目の特定
* 追加で調査すべきポイントの提示

AIの出力はユーザーが入力した企業情報とは区別して表示する。根拠となる保存済み情報や情報源がある場合は、それらを確認できるようにする。

#### Latest News（Future Work / v0.1未実装）

対象企業に関する直近のニュースを軽量な範囲で取得する構想は、将来のMilestoneとして扱う。

将来実装する場合の初期範囲は、以下を想定する。

* 過去30日または90日のニュース
* 最大5件程度
* ニュースタイトル
* 公開日
* 情報源
* 元記事URL
* 取得できる場合はスニペット

ユーザーが必要なニュースを選択した場合、AIによる簡潔な要点整理を行う。要約がタイトルやスニペットのみに基づく場合は、その制限をユーザーに明示し、元記事URLを表示する。

ニュース結果は自動保存せず、ユーザーが必要と判断したものを企業の情報源として保存できるようにする。

ニュース記事の全文取得、クローリング、自動監視、バックグラウンド更新は将来の初期範囲にも含めない。

---

### 6.4 Selection Preparation

企業研究結果を、就活軸および個人の経験と結び付け、選考準備に利用できる「素材」として整理する。

#### Connections with Criteria and Experiences

企業との絶対的な相性やマッチングスコアは算出しない。代わりに、以下を整理する。

* 企業の特徴と就活軸の接点が強い項目
* 接点の根拠となる企業情報や情報源
* 関連する可能性がある個人の経験・エピソード
* 現時点では情報が不足している項目
* 面接、説明会、または追加調査で確認すべき質問

AIによる経験との接点は候補・提案として提示する。AIが使用する経験を決定したり、ユーザーの適性や就職先を断定したりしない。

#### Selection Materials

主な内容：

* 志望動機に利用できる企業側のポイント
* 自分の経験との接点候補
* 「なぜこの会社か」を考えるための材料
* 「なぜこの職種か」を考えるための材料
* 想定される面接質問
* 準備しておきたい質問
* 追加で調べるべき内容

完成したESや志望動機をAIが一方的に作成することを主目的とはしない。最終的な内容の選択、検証、表現はユーザー自身が行う。

---

## 7. v0.1 SQLite Data Model

v0.1では、`user_profile`、`job_axes`、`experiences`、`companies`、`sources`、`source_contents`、`ai_results`の7テーブルを使用する。AI出力の種類ごとに個別のテーブルは作成しない。

取得した根拠は、Company → Source → Source Content Snapshot（`companies` → `sources` → `source_contents`）の関係で保持する。

### 7.1 `user_profile`

ローカルユーザーの基本プロフィールを1件保存する。

* 志望職種
* 自由メモ
* 作成日時・更新日時

### 7.2 `job_axes`

複数の就活軸を保存する。

* 就活軸の内容
* 任意の説明
* 表示順
* 作成日時・更新日時

### 7.3 `experiences`

複数の経験・エピソードを独立して保存する。

* タイトル
* カテゴリ
* 短い要約
* 詳細
* 任意のスキル・タグ
* 作成日時・更新日時

### 7.4 `companies`

企業研究の基本情報を保存する。

* 企業名
* 主な事業
* 強み・特徴
* 経営戦略
* DX・AI関連施策
* 海外事業
* 採用職種・仕事内容
* 自由メモ
* 作成日時・更新日時

### 7.5 `sources`

企業ごとの情報源を保存する。

* 企業ID
* タイトル
* URL
* 情報源の種別
* 公開日
* メモ

### 7.6 `source_contents`

Source URLから取得した本文を、取得時点のSnapshotとして保存する。再取得時は既存本文を上書きせず、新しいSnapshotを追加する。

* Source ID
* 取得元URL・最終URL
* ページタイトル
* Content type
* 取得本文
* 文字数・省略状態
* 取得日時・作成日時

### 7.7 `ai_results`

企業に対して生成されたAI支援結果を保存する。

* 企業ID
* 結果種別
* 生成内容
* 生成日時

AI生成結果はユーザー入力データを上書きせず、別データとして保持する。生成日時を表示し、元の企業情報、就活軸、または経験が変更された場合には、結果が古くなっている可能性をユーザーが判断できるようにする。

将来のニュース検索結果は原則として一時的に扱う。ユーザーが保存を選択したニュースは`sources`に、選択したニュースのAI要約は必要に応じて`ai_results`に保存する設計を想定する。

---

## 8. v0.1 Project Structure

```text
careerlens/
├── app.py
├── pages/
│   ├── 1_my_profile.py
│   ├── 2_company_research.py
│   ├── 3_research_assistant.py
│   └── 4_selection_preparation.py
│
├── careerlens/
│   ├── __init__.py
│   ├── database.py
│   ├── ai_service.py
│   ├── source_retrieval.py
│   ├── prompts.py
│   └── ui.py
│
├── data/
│   └── .gitkeep
│
├── tests/
│   ├── test_database.py
│   ├── test_ai_service.py
│   ├── test_source_retrieval.py
│   ├── test_*_ui.py
│   └── test_ui.py
│
├── docs/
│   ├── product-requirements.md
│   ├── architecture.md
│   ├── portfolio-presentation.md
│   └── v0.1-release-check.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── LICENSE
```

アーキテクチャは初心者にも理解しやすい構成を維持し、通常のPython関数を中心に実装する。共通UIはdesign tokensとnavigationに限定し、コントローラー層、Repositoryパターン、Dependency Injection、不要なクラス、大規模なUI component frameworkは導入しない。

---

## 9. Recommended Implementation Order

1. Application shell + SQLite initialization
2. My Profile（志望職種・自由メモ）
3. Job-search criteria CRUD（追加・編集・削除・並べ替え）
4. Experiences CRUD（追加・編集・削除・一覧・詳細表示）
5. Company Research
6. Sources / URL management
7. AI Research Assistant
8. Webpage Content Retrieval
9. Evidence Snapshot Persistence
10. Evidence-backed AI Research
11. Controlled AI Adoption
12. 企業情報、就活軸、経験の接点整理 / Selection Preparation

外部APIを必要としない情報登録・保存機能を先に完成させ、その後にAIとWeb本文取得を追加する。Latest News連携はFuture Workとして扱う。

---

## 10. Out of Scope for v0.1

以下の機能は初期MVPでは実装しない。

* Company Comparison
* 内定・Offer比較
* AIによる就職先の自動推薦
* 企業との絶対的なマッチングスコア
* ESや志望動機の完全自動作成
* 自動応募
* ユーザー認証・マルチユーザー対応
* 非同期ワーカーやバックグラウンド処理
* ニュースのバックグラウンド監視
* 大量のニュース記事の自動収集
* ニュース記事の全文取得
* Latest News検索・ニュースAPI連携
* PDF本文取得
* Webクローラー
* SNS情報の自動分析
* Vector Database

これらは必要性を検証した上で、将来のバージョンで検討する。

---

## 11. Technology Stack

v0.1では以下の構成を使用する。

* **Python** — application logic
* **Streamlit** — four-page web application UI
* **SQLite** — local-first data storage
* **OpenAI Responses API** — structured AI-assisted research
* **HTTPX / Beautiful Soup** — safe webpage retrieval and text extraction
* **pytest / unittest / Streamlit AppTest** — automated regression testing
* **Git / GitHub** — version control and development history

ライブラリは実際に必要になった段階で追加し、MVPに不要な依存関係を増やさない。技術構成は開発過程で必要に応じて変更する。

---

## 12. Development Principles

CareerLensの開発では以下を重視する。

1. 実際の就職活動で利用できること
2. AIに企業研究やキャリア判断を任せすぎないこと
3. ユーザー入力とAI生成情報を明確に区別すること
4. 情報源と元URLを可能な限り確認できること
5. 根拠が不足する場合は推測せず「情報不足」と示すこと
6. AIによる分析や経験の接点は提案として扱い、最終判断はユーザーが行うこと
7. 個人の経験をAIへ送信する処理は、ユーザーの明示的な操作によってのみ実行すること
8. 小さな機能単位で開発・検証すること
9. GitHub上に開発過程と意思決定を残すこと
10. MVPに不要な機能や抽象化を増やしすぎないこと

---

## 13. Future Ideas

MVP完成後、必要に応じて以下を検討する。

* Company Comparison
* 就活軸の変更履歴
* インターン・面接後の企業評価
* IR・統合報告書の読み込み
* ニュースと企業研究情報の自動連携
* 選考進捗管理
* レポート出力
