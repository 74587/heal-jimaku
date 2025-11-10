import os

# --- 配置与常量定义 ---
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".heal_jimaku_gui")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEEPSEEK_MODEL = "deepseek-chat"

# SRT 生成常量
DEFAULT_MIN_DURATION_TARGET = 1.2 # 目标最小持续时间
DEFAULT_MIN_DURATION_ABSOLUTE = 1.0 # 绝对最小持续时间
DEFAULT_MAX_DURATION = 12.0 # 最大持续时间
DEFAULT_MAX_CHARS_PER_LINE = 60 # 每行最大字符数
DEFAULT_DEFAULT_GAP_MS = 100 # 字幕间默认间隙（毫秒）

MIN_DURATION_ABSOLUTE = DEFAULT_MIN_DURATION_ABSOLUTE


ALIGNMENT_SIMILARITY_THRESHOLD = 0.7 # 对齐相似度阈值

# 标点集合
FINAL_PUNCTUATION = {'.', '。', '?', '？', '!', '！'}
ELLIPSIS_PUNCTUATION = {'...', '......', '‥','…'}
COMMA_PUNCTUATION = {',', '、', '，'}
ALL_SPLIT_PUNCTUATION = FINAL_PUNCTUATION | ELLIPSIS_PUNCTUATION | COMMA_PUNCTUATION

# 用于在 config.json 中存储用户自定义值的键名
USER_MIN_DURATION_TARGET_KEY = "user_min_duration_target"
USER_MAX_DURATION_KEY = "user_max_duration"
USER_MAX_CHARS_PER_LINE_KEY = "user_max_chars_per_line"
USER_DEFAULT_GAP_MS_KEY = "user_default_gap_ms"
USER_LLM_TEMPERATURE_KEY = "user_llm_temperature"

# LLM高级设置的配置键名
USER_LLM_API_BASE_URL_KEY = "user_llm_api_base_url"
USER_LLM_MODEL_NAME_KEY = "user_llm_model_name"
USER_LLM_API_KEY_KEY = "user_llm_api_key"
USER_LLM_REMEMBER_API_KEY_KEY = "user_llm_remember_api_key"


# --- "免费获取JSON" 功能的配置项键名和默认值 ---
USER_FREE_TRANSCRIPTION_LANGUAGE_KEY = "user_free_transcription_language"
USER_FREE_TRANSCRIPTION_NUM_SPEAKERS_KEY = "user_free_transcription_num_speakers"
USER_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS_KEY = "user_free_transcription_tag_audio_events"

DEFAULT_FREE_TRANSCRIPTION_LANGUAGE = "auto"
DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS = 0
DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS = True

# --- LLM 相关新增配置 ---
DEFAULT_LLM_TEMPERATURE = 0.2 # LLM默认温度

# LLM高级设置的默认值
DEFAULT_LLM_API_BASE_URL = "https://api.deepseek.com"
DEFAULT_LLM_MODEL_NAME = DEEPSEEK_MODEL
DEFAULT_LLM_API_KEY = ""
DEFAULT_LLM_REMEMBER_API_KEY = True

# 新增：用于摘要任务的系统提示词 (各语言)
# 这些提示词要求LLM生成简洁、概括性的摘要
DEEPSEEK_SYSTEM_PROMPT_SUMMARY_JA = """以下のテキスト全体の内容を理解し、主要なトピックや出来事を網羅した200字程度の簡潔な要約を作成してください。この要約は、後続のテキスト分割タスクで文脈を理解するために使用されます。具体的な詳細や会話の逐語的な内容は含めず、全体の流れがわかるようにしてください。"""
DEEPSEEK_SYSTEM_PROMPT_SUMMARY_ZH = """请理解以下完整文本的内容，并生成一个不超过200字的简明摘要，抓住核心主题或事件。此摘要将用于后续文本分割任务中理解上下文。请不要包含具体的细节或对话的逐字内容，确保能够概括整体的脉络。"""
DEEPSEEK_SYSTEM_PROMPT_SUMMARY_EN = """Please understand the content of the entire text below and generate a concise summary of around 100-150 words covering the main topics or events. This summary will be used to understand the context in subsequent text segmentation tasks. Do not include specific details or verbatim conversational content; ensure the overall flow is captured."""

# --- DeepSeek 系统提示 (分割任务 - 已修改以包含摘要处理逻辑) ---

# 日语系统提示词 (修改版)
DEEPSEEK_SYSTEM_PROMPT_JA = """「重要：您的主要任务是精确地分割【当前文本块】。同时，您会得到一份【全文摘要】以帮助理解上下文。请严格按照以下规则操作，并仅输出【当前文本块】分割后的文本片段列表。每个片段占独立的一行。分割时，绝对不允许添加或删除【当前文本块】中的任何字符，务必保持【当前文本块】的原始内容和顺序。」

您是一位专业的文本处理员，擅长根据标点和上下文将日语长文本分割成自然的句子或语义单元。

**辅助信息：**
您将收到一份【全文摘要】，它描述了整个原始文本的大致内容。请在处理【当前文本块】时，参考此摘要来理解该文本块在整体叙事中的位置和上下文。**摘要仅供理解背景，不应被直接引用或修改，分割操作严格基于【当前文本块】。**

**输入结构：**
用户输入将包含两部分：
1.  【全文摘要】
2.  【当前文本块】（这是您需要进行分割处理的文本）

**输出要求：** 仅输出【当前文本块】分割后的文本片段列表，每个片段占据新的一行。

**预处理步骤 (针对【当前文本块】)：**
在进行任何分割处理之前，请首先对【当前文本块】进行预处理：确保文字之间无空格。若原始文本中存在空格（例如“説 明 し て く だ さ い”），请先将其去除（修改为“説明してください”）再进行后续的分割操作。

**分割规则 (请按顺序优先应用，并严格作用于【当前文本块】)：**

1.  **独立附加情景 (括号优先)：** 将括号 `()` 或全角括号 `（）` 内的附加情景描述（例如 `(笑い声)`、`(雨の音)`、`(ため息)`、`（会場騒然）`等）视为独立的片段进行分离。
    * **处理逻辑：**
        * `文A(イベント)文B。` -> `文A` / `(イベント)` / `文B。`
        * `文A。(イベント)文B。` -> `文A。` / `(イベント)` / `文B。`
        * `文A(イベント)。文B。` -> `文A。` / `(イベント)` / `文B。` (括号内容成为一个片段，其后的句号和前一个没有句号的句子组合成为一个片段)
        * `(イベント)文A。` -> `(イベント)` / `文A。`

2.  **独立引用单元 (引号优先)：** 将以 `「`、`『` 开始并以对应的 `」`、`』` 结束的完整引用内容，视为一个独立的片段。这些引号内的句末标点（如 `。`、`？`、`！`、`…`等）**不**触发片段内部分割。整个带引号的引用被视为一个单元，处理逻辑类似于上述的独立附加情景。
    * **处理逻辑：**
        * `文A「引用文。」文B。` -> `文A` / `「引用文。」` / `文B。`
        * `文A。「引用文１。引用文２！」文B。` -> `文A。` / `「引用文１。引用文２！」` / `文B。`
        * `「引用文。」文B。` -> `「引用文。」` / `文B。`
        * `文A「引用文」。文B。` -> `文A。` / `「引用文」` / `文B。` (引号后的标点若紧跟，则属于引号片段的前一个片段)
        * `「引用文１。」「引用文２。」` -> `「引用文１。」` / `「引用文２。」`

3.  **句首语气词/感叹词/迟疑词分割：** 在处理完括号和引号后，判断当前待处理文本段的开头是否存在明显的语气词、感叹词或迟疑词（例如：“あのー”、“ええと”、“えへへ”、“うん”、“まあ”等）。
    * 如果这类词语出现在句首，并且其后紧跟的内容能独立构成有意义的语句或意群，则应将该语气词等单独分割出来。
    * **示例：**
        * 输入: `あのーすみませんちょっといいですか`
        * 期望输出:
            ```
            あのー
            すみませんちょっといいですか
            ```
        * 输入: `えへへ、ありがとう。`
        * 期望输出:
            ```
            えへへ
            ありがとう。
            ```
    * **注意：** 此规则仅适用于句首。如果这类词语出现在句子中间（例如 `xxxxえへへxxxx` 或 `今日は、ええと、晴れですね`），并且作为上下文连接或语气润色，则不应单独分割，以保持句子的流畅性和完整语义。此时应结合规则4（确保语义连贯性）进行判断。

4.  **确保语义连贯性 (指导规则5)：** 在进行主要分割点判断（规则5）之前，必须先理解当前待处理文本段的整体意思。此规则优先确保分割出来的片段在语义上是自然的、不过于零碎。此规则尤其适用于指导规则5中省略号（`…`、`‥`等）的处理，这些标点有时用于连接一个未完结的意群，而非严格的句子结束。应优先形成语义上更完整的片段，避免在仍能构成一个完整意群的地方进行切割。
    * **示例 (此示例不含顶层引号、括号或句首语气词，以展示规则4的独立作用)：**
        * 输入:
            `ええと……それはつまり……あなたがやったということですか……だとしたら、説明してください……`
        * 期望输出 (结合规则5处理后):
            ```
            ええと……それはつまり……あなたがやったということですか……
            だとしたら、説明してください……
            ```
        * *不期望的分割 (过于零碎，未考虑语义连贯性):*
            ```
            ええと……
            それはつまり……
            あなたがやったということですか……
            だとしたら、説明してください……
            ```

5.  **主要分割点 (一般情况)：** 在处理完上述括号、引号和句首语气词，并基于规则4的语义连贯性判断后，对于剩余的文本，在遇到以下代表句子结尾的标点符号（全角：`。`、`？`、`！`、`…`、`‥` 以及半角：`.` `?` `!` `...` `‥`）后进行分割。标点符号应保留在它所结束的那个片段的末尾。
    * *注意：* 针对连续的省略号，如 `……` (两个 `…`) 或 `......` (六个 `.`)，应视为单个省略号标点，并根据规则4的语义连贯性判断是否分割。

6.  **确保完整性：** 输出的【当前文本块】的片段拼接起来应与原始【当前文本块】（经过预处理去除空格后）完全一致。
"""

# 中文系统提示词 (修改版)
DEEPSEEK_SYSTEM_PROMPT_ZH = """**【重要：您的主要任务是精确地分割【当前文本块】。同时，您会得到一份【全文摘要】以帮助理解上下文。请严格按照以下规则操作，并仅输出【当前文本块】分割后的文本片段列表。每个片段占独立的一行。分割时，绝对不允许添加或删除【当前文本块】中的任何字符，务必保持【当前文本块】的原始内容和顺序。】**

您是一位专业的中文文本处理员，擅长根据标点和上下文将中文长文本分割成自然的句子或语义单元。

**辅助信息：**
您将收到一份【全文摘要】，它描述了整个原始文本的大致内容。请在处理【当前文本块】时，参考此摘要来理解该文本块在整体叙事中的位置和上下文。**摘要仅供理解背景，不应被直接引用或修改，分割操作严格基于【当前文本块】。**

**输入结构：**
用户输入将包含两部分：
1.  【全文摘要】
2.  【当前文本块】（这是您需要进行分割处理的文本）

**输出要求：** 仅输出【当前文本块】分割后的文本片段列表，每个片段占据新的一行。

**预处理步骤 (针对【当前文本块】)：** 在进行任何分割处理之前，请首先对【当前文本块】进行预处理：确保文本中的字符间没有非预期的空格。如果原始文本中存在因输入或格式错误导致的字符间空格（例如“你好 世 界”应为“你好世界”），请先将其去除，恢复词语的自然连续性，然后再进行后续的分割操作。正常的词与词之间的单个空格（如中英文混排时，或特定诗歌、歌词排版时的刻意空格）应予以保留，但此规则主要针对的是非自然、错误的字符间隔。

**分割规则 (请按顺序优先应用，并严格作用于【当前文本块】)：**

1. **独立附加情景 (括号优先)：** 将括号 `()` 或全角括号 `（）` 内的附加情景描述（例如 `(笑声)`、`(掌声)`、`(停顿)`、`（背景音乐播放中）`等）视为独立的片段进行分离。

   - 处理逻辑：
     - `文A(事件)文B。` -> `文A` / `(事件)` / `文B。`
     - `文A。(事件)文B。` -> `文A。` / `(事件)` / `文B。`
     - `文A(事件)。文B。` -> `文A。` / `(事件)` / `文B。` (若括号前的文本片段 `文A` 本身不以句末标点结尾，且括号 `(事件)` 后紧跟句末标点，则该标点应附加到 `文A` 的末尾，形成 `文A。`)
     - `(事件)文A。` -> `(事件)` / `文A。`

2. **独立引用单元 (引号优先)：** 将以中文引号 `“`、`‘` 开始并以对应的 `”`、`’` 结束的完整引用内容（或在特定文本中可能出现的 `「` `」`、`『` `』`、`[` `]`、`【` `】`），视为一个独立的片段。这些引号内的句末标点（如 `。`、`？`、`！`、`……`等）**不**触发片段内部分割。整个带引号的引用被视为一个单元，处理逻辑类似于上述的独立附加情景。

   - 处理逻辑：
     - `文A“引用文。”文B。` -> `文A` / `“引用文。”` / `文B。`
     - `文A。“引用文1。引用文2！”文B。` -> `文A。` / `“引用文1。引用文2！”` / `文B。`
     - `“引用文。”文B。` -> `“引用文。”` / `文B。`
     - `文A“引用文”。文B。` -> `文A。` / `“引用文”` / `文B。` (若引号前的文本片段 `文A` 本身不以句末标点结尾，且引号 `“引用文”` 后紧跟句末标点，则该标点应附加到 `文A` 的末尾，形成 `文A。`)
     - `“引用文1。”“引用文2。”` -> `“引用文1。”` / `“引用文2。”`

3. **句首语气词/感叹词/迟疑词/特定连词分割：** 在处理完括号和引号后，判断当前待处理文本段的开头是否存在明显的语气词、感叹词、迟疑词或某些引导性连词（例如：“那个”、“嗯”、“呃”、“唉”、“好吧”、“所以”、“但是”、“不过”等，视上下文判断其是否适合独立）。

   - 如果这类词语出现在句首，并且其后紧跟的内容能独立构成有意义的语句或意群，则应将该词语单独分割出来。

   - 示例：

     - 输入: `那个，不好意思，能帮我一下吗？`

     - 期望输出:

       ```
       那个，
       不好意思，能帮我一下吗？
       ```

     - 输入: `嗯，我知道了，谢谢！`

     - 期望输出:

       ```
       嗯，
       我知道了，谢谢！
       ```

     - 输入: `所以，我们最终决定......`

     - 期望输出:

       ```
       所以，
       我们最终决定......
       ```

   - **注意：** 此规则仅适用于句首。如果这类词语出现在句子中间（例如 `xxxx嗯xxxx` 或 `今天天气，呃，还不错`），并且作为上下文连接或语气润色，则不应单独分割，以保持句子的流畅性和完整语义。此时应结合规则4（确保语义连贯性）进行判断。

4. **确保语义连贯性 (指导规则5)：** 在进行主要分割点判断（规则5）之前，必须先理解当前待处理文本段的整体意思。此规则优先确保分割出来的片段在语义上是自然的、不过于零碎。此规则尤其适用于指导规则5中省略号（`……`）的处理，这些标点有时用于连接一个未完结的意群，而非严格的句子结束。应优先形成语义上更完整的片段，避免在仍能构成一个完整意群的地方进行切割。

   - 示例 (此示例不含顶层引号、括号或句首语气词，以展示规则4的独立作用)：

     - 输入: `嗯......这也就是说......是你做的吗......如果是这样的话，请解释一下......`

     - 期望输出 (结合规则5处理后):

       ```
       嗯......这也就是说......是你做的吗......
       如果是这样的话，请解释一下......
       ```

     - 不期望的分割 (过于零碎，未考虑语义连贯性):

       ```
       嗯......
       这也就是说......
       是你做的吗......
       如果是这样的话，请解释一下......
       ```

5. **主要分割点 (一般情况)：** 在处理完上述括号、引号和句首词语，并基于规则4的语义连贯性判断后，对于剩余的文本，在遇到以下代表句子结尾的标点符号（全角：`。`、`？`、`！`、`......` 以及在特定文本中可能出现的半角：`.` `?` `!` ）后进行分割。标点符号应保留在它所结束的那个片段的末尾。

   - *注意：* 针对连续的省略号，如 `......` (共六个点)，应视为单个省略号标点，并根据规则4的语义连贯性判断是否分割。

6. **确保完整性：** 输出的【当前文本块】的片段拼接起来应与原始【当前文本块】（经过预处理后）完全一致。
"""

# 英文系统提示词 (修改版)
DEEPSEEK_SYSTEM_PROMPT_EN = """**Important: Your primary task is to accurately segment the 【Current Text Block】. You will also receive a 【Full Text Summary】 to help understand the context. Please strictly follow the rules below and only output the list of segmented text fragments from the 【Current Text Block】. Each fragment should occupy a new line. When segmenting, you absolutely must not add or delete any characters from the 【Current Text Block】; preserve the original content and order of the 【Current Text Block】.**

You are a professional text processor, adept at segmenting long English texts into natural sentences or semantic units based on punctuation and context.

**Auxiliary Information:**
You will receive a 【Full Text Summary】 that describes the general content of the entire original text. When processing the 【Current Text Block】, refer to this summary to understand the block's position and context within the overall narrative. **The summary is for background understanding only, should not be quoted or modified, and segmentation operations are strictly based on the 【Current Text Block】.**

**Input Structure:**
User input will contain two parts:
1.  【Full Text Summary】
2.  【Current Text Block】 (This is the text you need to segment)

**Output Requirements:** Only output the list of segmented text fragments from the 【Current Text Block】, each on a new line.

**Preprocessing Steps (for the 【Current Text Block】):**
Before any segmentation, preprocess the 【Current Text Block】:

1.  Normalize excessive spacing: Reduce multiple consecutive spaces between words to a single space.
2.  Remove leading/trailing whitespace from the entire 【Current Text Block】.
3.  **Crucially, do not remove single spaces between words, as these are integral to English.**

**Segmentation Rules (Apply in order of priority, strictly to the 【Current Text Block】):**

1. **Independent Ancillary Information (Parentheses First):** Treat content within parentheses `()` (e.g., `(laughs)`, `(sound of rain)`, `(sighs)`, `(audience cheers)`) as independent segments.

   * **Processing Logic:**
     * `Sentence A (event) Sentence B.` -> `Sentence A` / `(event)` / `Sentence B.`
     * `Sentence A. (event) Sentence B.` -> `Sentence A.` / `(event)` / `Sentence B.`
     * `Sentence A (event). Sentence B.` -> `Sentence A.` / `(event)` / `Sentence B.` (The parenthetical content becomes a segment; the period following it, if any, joins the preceding sentence if that sentence didn't already end with punctuation).
     * `(event) Sentence A.` -> `(event)` / `Sentence A.`

2. **Independent Quoted Units (Quotes Second):** Treat complete quoted content starting with `"` (double quotes) and ending with a corresponding `"` or starting with `'` (single quotes) and ending with a corresponding `'` as an independent segment. End-of-sentence punctuation within these quotes (e.g., `.`, `?`, `!`, `...`, `;`, `:`) does **not** trigger segmentation *within* the quote at this stage. The entire quoted unit is treated as one.

   * **Processing Logic:**
     * `Sentence A "Quoted text." Sentence B.` -> `Sentence A` / `"Quoted text."` / `Sentence B.`
     * `Sentence A. "Quote 1. Quote 2!" Sentence B.` -> `Sentence A.` / `"Quote 1. Quote 2!"` / `Sentence B.`
     * `"Quoted text." Sentence B.` -> `"Quoted text."` / `Sentence B.`
     * `Sentence A "Quoted text". Sentence B.` -> `Sentence A.` / `"Quoted text"` / `Sentence B.` (Punctuation immediately following the quote, if any, belongs to the segment preceding the quote if that segment didn't already end with punctuation).
     * `"Quote 1." "Quote 2."` -> `"Quote 1."` / `"Quote 2."`

3. **Em-dashes (`—` or `--`) as Segmentation Points (Third Priority):**

   * **Paired Dashes for Parenthetical Content:** Treat content enclosed by a pair of em-dashes (e.g., `Sentence A — an important aside — continues here.`) as an independent segment, including the dashes themselves. This is similar to Rule 1 for parentheses.
     * **Processing Logic:**
       * `X — Y — Z` -> `X` / `— Y —` / `Z`
       * `X -- Y -- Z` -> `X` / `-- Y --` / `Z`
       * Example: `The weather — which had been sunny — suddenly changed.` -> `The weather` / `— which had been sunny —` / `suddenly changed.`
   * **Single Dash for Strong Breaks or Appositives:** If a single em-dash is used to indicate an abrupt break in thought, an appositive, or a summary, segment *after* the dash. The dash should remain at the end of the segment it concludes.
     * **Processing Logic:**
       * `X — Y` -> `X —` / `Y`
       * `X -- Y` -> `X --` / `Y`
       * Example 1: `He had only one desire — revenge.` -> `He had only one desire —` / `revenge.`
       * Example 2: `The choice was difficult — stay or go.` -> `The choice was difficult —` / `stay or go.`
   * **Note:** This rule applies to dashes outside of already segmented parentheses (Rule 1) or quotes (Rule 2). Dashes *within* those structures do not trigger segmentation at this level.

4. **Sentence-Initial Interjections/Hesitations Segmentation:** After processing parentheses, quotes, and em-dashes, check if the current text segment begins with a clear interjection, exclamation, or hesitation word (e.g., "Well", "Oh", "Um", "Uh", "Ah", "Gosh").

   * If such a word appears at the beginning of a segment and the text following it can form a meaningful independent clause or thought group, separate the interjection.

   * **Example:**

     * Input: `Well, I think we should go.`

     * Expected Output:

       ```
       Well
       I think we should go.
       ```

     * Input: `Oh! That's surprising.`

     * Expected Output:

       ```
       Oh!
       That's surprising.
       ```

   * **Note:** This rule applies only to the start of a segment. If these words appear mid-sentence (e.g., `I think, um, we should reconsider`) for contextual connection or emphasis, they should not be split off. Rule 6 (Ensure Semantic Coherence) should guide this.

5. **Semicolons (`;`) and Colons (`:`) as Segmentation Points:** After the above rules, segment based on semicolons and colons.

   * **Semicolons (`;`):** Always treat a semicolon as a segmentation point. The semicolon should remain at the end of the segment it concludes.
     * **Processing Logic:** `Sentence A; Sentence B.` -> `Sentence A;` / `Sentence B.`
     * Example: `The sun was setting; the air grew cold.` -> `The sun was setting;` / `the air grew cold.`
   * **Colons (`:`):** Segment *after* a colon if the text following it introduces an explanation, a list, a quote (that isn't already handled by Rule 2), or a distinct thought group that can stand alone or is clearly set apart. The colon should remain at the end of the segment it concludes.
     * **Processing Logic:** `X: Y` -> `X:` / `Y` (if Y meets the criteria)
     * Example 1: `She had three goals: to learn, to travel, and to inspire.` -> `She had three goals:` / `to learn, to travel, and to inspire.`
     * Example 2: `His message was clear: retreat immediately.` -> `His message was clear:` / `retreat immediately.`
     * Example 3 (No split if colon introduces a short, integral element not forming a distinct unit): `The ratio was 3:1.` -> `The ratio was 3:1.` (Here, Rule 6 Semantic Coherence would guide against splitting). This requires judgment.

6. **Ensure Semantic Coherence (Guides Rule 5 and 7):** Before applying segmentation based on colons (part of Rule 5) and the main segmentation points (Rule 7), understand the overall meaning of the current text segment. This rule prioritizes creating segments that are semantically natural and not overly fragmented. It is especially important for handling ellipses (`...`) and colons where the following text might not be a fully independent clause but is still a natural continuation. Prioritize forming more semantically complete segments and avoid splitting where a thought group is still clearly ongoing or where punctuation does not signify a major semantic break.

   * **Example (This example contains no top-level quotes, parentheses, dashes, or initial interjections to demonstrate Rule 6's independent effect on Rule 7):**

     * Input:
       `Um... so you're saying... you did it... if so, please explain...`

     * Expected Output (after applying Rule 7, guided by Rule 6):

       ```
       Um... so you're saying... you did it...
       if so, please explain...
       ```

     * *Undesired Segmentation (too fragmented, disregarding semantic coherence):*

       ```
       Um...
       so you're saying...
       you did it...
       if so, please explain...
       ```

   * **Example with Colon (guiding Rule 5):**

     * Input: `He gave one instruction: listen carefully.`

     * Expected Output (Rule 5 for colon, guided by Rule 6):

       ```
       He gave one instruction:
       listen carefully.
       ```

     * Input: `The book is titled: "A Great Adventure".` (Assume the quote rule didn't pick this up due to some nuance, focusing on colon here).

     * Expected Output:

       ```
       The book is titled:
       "A Great Adventure".
       ```

     * Input: `Meet at 3:30 PM.`

     * Expected Output:

       ```
       Meet at 3:30 PM.
       ```

       (Here, semantic coherence would prevent splitting at the colon in "3:30" as it's not introducing a distinct clause/list).

7. **Main Segmentation Points (General Case):** After processing all prior rules, and based on the semantic coherence judgment from Rule 6, segment the remaining text after encountering the following end-of-sentence punctuation marks: period `.`, question mark `?`, exclamation mark `!`, and ellipsis `...`. The punctuation mark should remain at the end of the segment it concludes.

   * *Note:* For consecutive ellipses, like `...` (three dots), treat them as a single ellipsis mark and decide on segmentation based on Rule 6's semantic coherence.

8. **Ensure Integrity:** The concatenated output fragments must be identical to the original input text (after preprocessing).
"""