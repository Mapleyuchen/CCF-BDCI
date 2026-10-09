# **提升科研论文自动生成Agent新颖性的前沿方法与系统架构深度研究报告**

在大语言模型（LLM）与科学发现（AI for Science）深度融合的背景下，人工智能正推动科研范式从基础的自动化辅助工具向具备完全自主性的“AI科学家”演进。根据当前学术界对大模型在科学发现中自主性等级的划分，人工智能科研系统可分为作为特定任务执行者的底层工具（Level 1）、具备复杂信息处理与初步推演能力的分析师（Level 2），以及能够主导完整科学研究生命周期的自主科学家（Level 3）1。近年来，诸如Sakana AI推出的The AI Scientist等先锋系统，已经成功展示了从开放式思维发散、代码编写、实验执行、结果可视化到最终撰写LaTeX格式论文及模拟同行评审的端到端闭环能力2。这种高度集成的自动化流程将单篇机器学习研究论文的生成成本大幅压缩至约十五美元，极大地扩展了人工智能在科研生产力层面的想象空间3。  
然而，随着此类自主科研Agent被广泛部署和深入评估，一个严峻的核心瓶颈日益凸显：由大语言模型主导生成的科研论文普遍面临新颖性（Novelty）不足的困境。实证分析与专家评估表明，现有AI科学家生成的科学想法往往局限于对现有文献的微小参数调整或已知方法的平庸组合，缺乏突破领域认知边界的原创性创新6。在复杂的自动化文献审查阶段，模型的判断经常出现严重偏差，不仅难以有效甄别具有高价值的新颖概念，反而容易将冗余的渐进式工作误判为重大创新7。这种现象的根本原因在于，大语言模型在本质上是基于海量历史语料训练的概率模型，其默认生成策略倾向于输出高概率的常规序列，而在科学发现领域，真正的突破性创新（Extrapolation）恰恰位于概率分布的长尾区域。传统的检索增强生成（RAG）或简单的零样本提示（Zero-shot Prompting）技术，使得系统极易受到高度相关但缺乏新意的参考论文影响，进而导致生成的科研方案逻辑同质化、技术创新匮乏8。  
为了突破这一瓶颈，提升科研论文自动生成Agent生成论文的新颖性，学术界在近期的顶级会议（如NeurIPS、ICLR、ACL、NAACL）及前沿预印本平台上，提出了一系列全新的方法论与系统架构。这些前沿技术涵盖了从微观的对抗性提示工程、多智能体交互生态，到宏观的树状博弈搜索、质量-多样性空间遍历，以及更为客观严谨的新颖性量化测量算法。本报告将对这些最新的前沿探索进行深度剖析，为设计下一代具备顶会级创新能力的高新颖性科研论文自动生成Agent提供系统性的理论支撑与架构设计蓝图。

## **大语言模型科学创新瓶颈的认知机制与架构缺陷**

要系统性地提升科研Agent生成论文的新颖性，必须首先解构现有大语言模型在科学构思（Ideation）与假设生成（Hypothesis Generation）阶段陷入平庸的内在机理。认知科学将创造力划分为心理创造力（P-creativity，即对系统或个体自身是全新的）和历史创造力（H-creativity，即对整个人类历史和现有知识库是全新的）9。当前大语言模型的困境在于，凭借其庞大的预训练知识库，系统能够轻易产生P-creativity层面的联想，但在面对需要突破现有科学范式、触达H-creativity边界的任务时却显得力不从心。  
这一局限性首先源于系统在假设生成阶段的搜索空间坍缩。在一项关于神经算子（Neural Operator）架构发现的消融实验中，研究人员构建了一个包含大语言模型规划者（Planner）和规则规划者的虚拟AI科学社区进行对比测试10。结果揭示了显著的无免费午餐（No-free-lunch）现象：虽然大语言模型能够发现参数精简的多族混合架构，但其审查代理（Reviewer Agent）在给出评估理由时，有高达百分之九十七的概率引用“准确性（Accuracy）”作为核心依据，而引用“新颖性（Novelty）”的比例仅占百分之二十六10。这表明，在缺乏强力干预的情况下，模型会自发地向已知高准确率的保守解空间坍缩，从而在底层逻辑上压制了对未知新颖架构的探索。  
其次，基于纯语言模型的置信度反馈机制存在严重的对齐偏差。在科学发现的自我完善循环中，系统高度依赖内部的置信度来进行假设筛选与迭代。然而，大模型往往对其生成的符合常规语法和表面科学连贯性的低质假设表现出极高的过度自信，而对那些可能违背直觉但具有深刻科学价值的非正统假设缺乏信心11。这种置信度错位导致了一种隐性的“奖励作弊（Reward Hacking）”，即模型在自我评估时不断强化虚假的相关性，反复利用其内部评分机制的漏洞，最终输出表面逻辑自洽但缺乏实质科学创新的空洞论文11。  
最后，传统文献检索引擎固化的语义匹配模式阻碍了跨领域的类比推理。经典的科研Agent通常使用检索增强生成技术召回与当前查询语义最接近的论文。这种基于余弦相似度的线性检索，使得模型被死死锁定在单一子领域的“舒适区”内。认知心理学研究表明，人类科学家的重大创新往往得益于跨领域的类比推理（Cross-domain analogical reasoning），而当前的单线检索机制阻断了模型接触远距离知识节点的可能性，从而扼杀了引发颠覆性科学构思的外部刺激8。

## **提示工程与认知路径重构：突破模型的局部最优**

在单体Agent的构思与生成环节，通过引入特定的对抗性约束规则和复杂的逻辑演进链条，可以有效迫使模型脱离高概率的常规路径，进入更具原创性的解空间。

### **拒绝提示（Denial Prompting）与逆向约束机制**

传统的科学创新提示策略通常依赖正向指令，例如直接要求模型“提出一个新颖的科研想法”。然而，最新的研究表明，通过对抗性查询（Adversarial Queries）和增量约束，能够更深刻地激发模型的发散性思维11。拒绝提示（Denial Prompting）便是一种通过系统性剥夺模型使用常规解决方案权利，从而强制其探索低概率创新区域的新型提示架构9。  
在拒绝提示的算法框架下，科研Agent在生成初始的研究假设或解决方案后，会触发一个专用的技术检测网络（Technique Detection）。该网络负责剖析初步方案，提取其中使用的核心“原子技术”或传统范式组件。随后，系统将这些被识别出的常规方法添加到动态更新的“约束列表（Constraint List）”中，并在下一轮生成迭代中，将该列表作为绝对的硬性约束注入提示词，要求模型在不使用列表中任何技术的前提下重新解决该科研问题9。随着迭代次数的增加，约束列表不断膨胀，模型所有熟悉的常规路径均被封锁，这种被刻意营造的极端反常环境（Unconventional environment）迫使系统必须调动其深层语义空间中极少被激活的知识网络，从而孕育出真正的创新策略13。  
为评估这种对抗性约束的效果，研究人员构建了NeoCoder数据集，并提出了一种名为NeoGauge的客观度量指标。NeoGauge同时融合了收敛性思维（验证生成的科学方案是否严密遵守了庞大的负向约束链条）与发散性思维（通过将方案与历史人类解决方案对比来衡量历史创造力）9。实证分析表明，引入拒绝提示后，大模型在应对复杂技术难题时，其产出前所未有解决方案的概率显著增加9。在科研论文自动生成的实践中，这意味着系统可以通过拒绝提示强制Agent摒弃烂熟于心的标准网络架构或经典的实验设计基准，迫使其合成全新的架构范式，从而在源头上保障科研想法的独创性。

### **思想链条（Chain of Ideas, CoI）与动态演进建模**

除了通过负向约束限制模型的行为空间，如何正向引导模型进行深刻的历史文献演进推演，是提升科研想法深度与新颖性的另一大支柱。Chain-of-Ideas (CoI) 框架提出了一种旨在模拟人类资深研究员深度思考过程的智能体机制8。人类科学家在构思新课题时，并非仅仅对检索到的离散摘要进行简单总结，而是致力于理清某一特定技术路线的历史演变脉络与未来趋势。  
CoI智能体在接收到初始研究主题后，首先识别出具有奠基意义的核心目标论文（Anchor Paper）。以此为锚点，系统在学术文献库中同时向两个时间维度展开知识追踪：向前追溯（Backward tracing）探寻该核心思想的理论起源与底层假设，向后追踪（Forward tracing）则梳理该思想被后续研究者如何改良与应用8。这一复杂的追踪过程将原本孤立、零散的文献实体，重构成一条由多篇论文按逻辑与时间顺序排列的思想演进链条（形式化表示为 ![][image1]）8。  
在成功构建多条反映领域内不同技术流派演进趋势的思想链条后，大语言模型被置于这一宏大的时空知识背景中，被要求预测该领域的下一个自然演进节点，并通过逐步巩固和迭代的新颖性审查机制，精雕细琢出未来的研究方向8。这种做法极大缓解了模型在面对海量无序文献时产生的信息过载与逻辑断裂。此外，诸如GoAI等衍生框架进一步将这种线性序列扩展为更为立体的学术思想知识图谱。在图谱中，系统不仅记录引文关系，还深入解析引文背后的语义语境，并赋予不同参考文献动态权重。Agent通过在这张具有方向性和历史厚度的图谱上游走，能够精准识别出技术发展的空白区域与潜在的交叉融合点16。

| 评估方法/框架 | 核心算法机制 | 评估形式 | 性能表现/特点 |
| :---- | :---- | :---- | :---- |
| **Denial Prompting** | 增量施加约束列表，禁止使用已检测到的常规技术 | NeoGauge指标（结合收敛性与发散性历史比对） | 显著提升H-creativity，迫使模型跳出舒适区9 |
| **Chain-of-Ideas (CoI)** | 构建 ![][image2] 思想演进链条进行历史趋势外推 | Idea Arena Elo积分圆桌锦标赛（GPT-4o/人类双重评估） | 超越GPT-Researcher与基线RAG达108及56 Elo分17 |
| **GoAI** | 融合引文关系与语义信息的学术思想图谱动态探索 | 结构化思维新颖度审查 | 强化了复杂关联发现，降低幻觉与平庸生成的风险16 |

在评估层面，CoI框架首创了名为Idea Arena的评价体系。由于生成式构思的开放性使得传统的绝对评分机制极不稳定，Idea Arena采用类似国际象棋的Elo积分系统和瑞士轮锦标赛（Round-Robin tournament）规则。在这个竞技场中，先进的大语言模型裁判对不同基线方法生成的研究想法进行成对比较（Pairwise comparison），并从新颖性、重要性、清晰度、可行性和预期有效性等维度进行综合判决17。严谨的实验结果显示，CoI不仅在模型主导的锦标赛中拔得头筹，在经过10位人类资深研究员的盲评中，同样以压倒性优势击败了AI-Scientist和GPT-Researcher等基线系统。值得注意的是，CoI智能体生成每一个候选高质量想法及配套实验设计的计算成本仅为0.50美元，展现出极高的经济性与规模化潜力17。

## **基于搜索与演化博弈的轨迹优化：平衡质量与多样性**

若提示工程是对生成节点本身进行局部基因重组，那么将启发式搜索算法与大语言模型结合的推理期（Inference-time）扩展，则是系统性遍历庞大假设空间的宏观战略。科学探索的本质是一个复杂的高维多目标搜索问题。为了在兼顾严谨可行性的同时最大化原创性，前沿研究开始将演化计算与树搜索算法引入科研Agent的系统架构中。

### **质量-多样性（Quality-Diversity）演化搜索与IDEAgent**

在多目标优化视域下，传统的科学发现系统极易陷入单极优化的陷阱。如果系统一味追求逻辑上的绝对正确与流程上的无懈可击，其往往会收敛于产生大量相互极其相似且微不足道的低风险想法；反之，若系统仅仅被鼓励追求新颖，则会生成大量脱离物理现实、存在致命逻辑漏洞的学术幻觉18。为了打破这一僵局，IDEAgent框架创造性地将科学构思形式化为质量-多样性（Quality-Diversity, QD）搜索问题18。  
IDEAgent的核心理念在于，利用多智能体网络管理并维持一个庞大的“思想谱系（Idea Lineages）”。在该范式中，质量（Quality）被严谨地定义为科研方案的非显而易见性、逻辑健全性以及具体规范的清晰度；多样性（Diversity）则要求系统在生成的一系列想法中，确保每一个方案在底层因果机制和具体干预手段上均与其余方案具有实质性的差异18。  
在系统运行期间，IDEAgent并未采用简单的后置过滤，而是引入了多维度的内部反馈循环。通过设立专门的速记员智能体（Stenographer），将冗长松散的草案精炼为包含核心元素的标准五元组。随后，评估模块从八个正交轴（包括失效模式、因果诊断、干预策略等核心技术特征）对生成的配对想法进行细粒度的交叉比对18。在保证质量的环节，智能体根据多维反馈对存在逻辑瑕疵的方案进行靶向修复与精炼，使得迭代出的高质量子代逐渐取代原始的父代草案；在维护多样性的环节，系统通过引入轻量级的顺序记忆（Sequential Memory），将新生想法与三大知识池——已完成的高质量想法集、历史祖先演化集以及被明确拒绝的失败提案集——进行严格的排他性校验18。  
在计算最终的多样性收益时，IDEAgent放弃了简单粗暴的成对距离平均法，转而采用图论中的“最大团（Maximum Clique）”算法，旨在从庞大的生成池中，精确提取出一个内部成员间两两多样性评分均高于严苛阈值的最大互斥想法子集，即产出量（Yield）18。横向基准对比表明，相较于如NOVA等其他先进的大语言模型科研构思基线，采用这种严密质量-多样性架构的IDEAgent，在维持科研方案高可行性和清晰度的同时，其合格的高新颖性科研想法产出率实现了惊人的3.89倍增长18。

### **蒙特卡洛纳什均衡自完善树（MC-NEST）**

在探索未知的科学假设空间时，如何有效分配计算资源以探索高潜力的低概率节点，是决定系统最终能否触达原创前沿的关键。近期提出的MC-NEST（Monte Carlo Nash Equilibrium Self-Refining Trees）框架，极其精妙地将蒙特卡洛树搜索（MCTS）与纳什均衡（Nash Equilibrium）博弈理论无缝整合到了科学假设的自主生成流程中22。  
在MC-NEST的逻辑映射中，整个未知的科研探索域被表征为一棵深不见底的搜索树。系统从一个代表初始平庸假设的根节点起步。在关键的节点扩展（Expansion）阶段，系统激活基于大语言模型的自反思与内部批判网络。具体而言，系统利用专业化提示生成针对当前科研假设的苛刻批评（Critique），随后要求生成模型根据该批评意见对假设进行结构性修改，产生一个更为完善的新方案，并将其作为子节点挂载到树中24。为了防止在广袤复杂的假设森林中迷失或过早陷入局部最优，MC-NEST采用了精巧的节点选择与置信度上限（UCT）等采样策略，从而在利用（Exploitation，深化已证实可行性较高的研究路径）与探索（Exploration，强行开辟极少被访问的新颖理论分支）之间维持着高度动态的平衡24。  
MC-NEST最具革命性的设计在于其引入纳什均衡博弈的终止条件。这意味系统内部的“批判者智能体”与“生成者智能体”之间形成了一种非合作博弈的关系。整个扩展和完善的过程将持续进行，直到两者的互动达到纳什均衡态——即生成模型提出的科研假设已经无懈可击，批判模型穷尽其内化知识也无法再挑出任何在逻辑可行性或常识层面的漏洞，同时任何进一步的激进修改都将导致可行性的大幅崩溃22。  
以该框架在合成肽序列优化这一真实生物化学场景中的应用为例。当目标是优化一段肽序列以实现细胞核定位和溶解度提升时，MC-NEST最初可能会生成一个常规的基线假设：将核定位信号（NLS）中的精氨酸替换为赖氨酸，以在维持核输入所需正电荷的同时，利用赖氨酸较小的空间位阻增强溶解度24。如果采用传统的单线生成模型，研究通常到此为止。然而，在MC-NEST的博弈树中，内部生化验证模块会敏锐地指出这种替换带来的致命权衡风险——可能导致受体结合亲和力的不可接受下降。面对这一批判反馈，系统并非放弃整个路径，而是通过树分支的横向扩展，主动引入额外的高级修饰策略（例如提出在富含甘氨酸的连接区中用丙氨酸进行精巧的替换，以在不引入新磷酸化位点的前提下维持分子的物理柔性）24。这种深度结合了领域特定验证与宏观树搜索的演进模式，确保了最终输出的假设不仅在思路上极其新颖，更在严苛的科学定律面前无懈可击。无独有偶，近期发布的最具影响力的The AI Scientist-v2版本，同样将其核心架构从初代的线性工作流升级为了Agentic Tree Search（智能体树搜索）技术，以此作为解决封闭循环中创新匮乏问题的核心战略25。

## **多智能体生态系统与图谱计算：模拟人类科学共同体的群体智慧**

现代重大科学发现往往不再是单个学者在孤岛上的灵光一现，而是跨学科共同体高频交流、激烈辩论与知识碰撞的结晶。为了在自动化框架中复现甚至超越人类科学共同体的创新爆发力，前沿架构设计开始大规模引入具备异构专长角色的多智能体协作网络、同行评审迭代机制以及超大规模的图谱计算引擎。

| 多智能体系统名称 | 核心网络架构与交互机制 | 应对新颖性不足的独特策略 | 适用科研阶段 |
| :---- | :---- | :---- | :---- |
| **ResearchAgent** | 层次化 ![][image3] 序列模型，内嵌模拟同行评审（ReviewingAgents） | 并行调用多维度审查，专门针对新颖性缺陷等低分项进行多轮定向修复迭代 | 实验设计与方法论规划26 |
| **SciAgents** | 生物启发式智能图推理多智能体交互网络 | 在数十万节点的知识图谱中强行寻找并推导远距离、跨域概念的潜在因果链接 | 跨学科概念发现与宏观理论推演28 |
| **Nova** | 迭代规划融合外部领域知识检索引擎 | 在瑞士轮锦标赛中由顶级模型（如Claude-3.5-Sonnet）进行成对较量，只保留Pareto前沿 | 最终想法的综合评估与筛选30 |
| **多智能体辩论** | 多异构角色（Persona）对抗性讨论与思维分歧机制 | 通过不同视角的高强度辩论揭露伪创新，提升逻辑推演的深度与事实正确率 | 科学假设合理性验证32 |

### **SciAgents与远距离跨域图推理**

在传统的科研文献检索与处理范式中，即便是性能最强的单体大模型，也无可避免地倾向于挖掘文献网络中那些连接紧密、引用频繁的近距离节点。这种“内卷式”的知识处理极大地限制了突破性创新的产生。SciAgents提出了一种颠覆性的基于生物启发的智能图推理（Intelligent Graph Reasoning）框架28。  
SciAgents的核心在于构建了一个包含数十万个离散科学概念及其复杂逻辑关系的超大规模底层知识图谱。与寻找已知联系不同，SciAgents中的多智能体网络被设定了一个极具挑战性的目标：专门去探寻图谱中那些距离极度遥远（Distant nodes）、在现有人类文献中几乎从未建立过明确联系的概念群29。在这个生态中，不同的智能体被赋予了截然不同的学科背景（例如一个专注于凝聚态物理，另一个精通分子生物学）。通过在知识图谱的拓扑结构上进行复杂的路径遍历与逆向推演，这些智能体能够通过多轮交互，自主建立起连接这两个遥远概念的潜在理论假设28。这一机制在硅基世界中完美复刻并加速了人类科学史上最珍贵的跨学科类比推理（Cross-domain analogical reasoning）过程，使得科研Agent能够从根本上跳出单一学科演进的死胡同，转向具有极高新颖性和范式颠覆潜力的交叉学科无人区探索12。

### **ResearchAgent：模拟同行评审与微观迭代**

微软研究院提出的ResearchAgent则将多智能体协作的重点放在了极具实操性的迭代打磨上26。该框架深刻汲取了Swanson提出的“基于文献的发现（Literature-based discovery）”这一经典理论的精髓，并将大模型主导的科学构思严格形式化为一个相互依赖的三元组序列：问题识别（![][image4]）、方法开发（![][image5]）与实验设计（![][image6]）26。  
ResearchAgent的创新之处在于其对外部信息的精细化摄取以及无情的多轮内部审查。系统首先不仅仅检索相似论文，更深入提取跨学科的“知识实体（Knowledge entities）”作为创新的素材库。在初始科研三元组 ![][image7] 提出后，系统会唤醒一组高度专业化的同行评审智能体（ReviewingAgents）。这些评审智能体在封闭沙盒内，模拟真实顶级学术会议的评审标准，并行从新颖性、严谨性、清晰度等五个严苛维度对该方案进行无情剖析与打分27。根据这些细粒度的评审反馈，系统将专门针对得分最低的薄弱环节（若发现方案缺乏原创性，则触发新一轮的深层实体检索与方法论重构）进行定向修复。工程实践与消融实验表明，这种迭代修复机制并非越多越好，通常在经过约三个轮次（Iterations）的高强度迭代后，科研方案的质量改进曲线会达到最优的平台期，实现了计算成本与创新质量的完美平衡26。  
类似的多智能体迭代优化思想也被Nova系统推向了极致。Nova框架通过紧密结合迭代规划和增强型的外部知识图谱检索，有效消除了模型单纯依赖内部参数时产生的知识幻觉。在最终的评估过滤阶段，Nova采用了创新的瑞士轮锦标赛（Swiss System Tournament）机制。利用Claude-3.5-Sonnet等顶级大模型作为零样本裁判，对所有迭代生成的候选方案进行高强度的成对厮杀。基于涵盖CVPR、ACL和ICLR等顶会的170篇高质量种子论文的基准测试结果显示，Nova系统产出排名前20%的顶尖创新想法的比例，是此前所有最先进方法的2.5倍30。此外，引入明确的多智能体辩论机制（Multi-Agent Debate），让具备不同学术偏好（如激进理论派与保守实验派）的智能体展开对抗性讨论，已被证明能有效粉碎认知盲区，剔除看似华丽实则经不起推敲的伪创新，沉淀出真正具备科学坚韧度的高质量原创思想32。

## **构建客观严谨的新颖性量化标尺：算法驱动的北极星指标**

科研论文自动生成系统在进行树搜索寻优或质量-多样性演化时，其进化方向完全取决于底层反馈回路提供的奖励信号（Reward Signal）。如果系统内部的奖励函数无法准确、客观地度量“什么是真正的新颖”，那么即使系统配备了最顶级的蒙特卡洛树搜索与辩论机制，最终也只能收敛于平庸。  
既往的文献自动分析和评估方法（如The AI Scientist早期版本或部分依赖AI-Researcher的方案）通常采取捷径，直接让大语言模型充当裁判（LLM-as-a-judge）来给新颖性打分。然而，研究界近期的《新颖性度量公理基准（Axiomatic Benchmark for Evaluation of Scientific Novelty Metrics）》揭露了一个冷酷的现实：所有现存的简单新颖性评价指标均无法稳定满足科学界公认的人类科研常态公理37。大模型在评估自身生成的科研想法时，存在极其严重的自我偏误（Self-bias）和位置偏误（Position bias），导致其自评的人类感观新颖度出现系统性的通货膨胀，从而令整个科研流水线的质量控制形同虚设6。

### **相对邻居密度算法（Relative Neighbor Density, RND）**

为了彻底根除大模型在主观评价上的不可靠性，学术界提出必须转向基于高维拓扑空间几何分布的客观物理测量算法。在这一探索路径中，相对邻居密度（Relative Neighbor Density, RND）算法脱颖而出，成为了当前最前沿、最具鲁棒性的跨学科新颖性评估标准38。  
RND算法的数学根基建立在高维语义嵌入空间之上。无论是庞大的历史人类文献库，还是由Agent刚刚炮制出的全新科研想法，都会统一交由极其强大的表征模型（如BGE-M3）处理，映射为全局语义宇宙中的一个个高维坐标点37。在此之前，学术界曾尝试过绝对局部密度算法（Absolute Local Density，例如历史相异度 Historical Dissimilarity），即简单计算待评估的新颖想法与历史库中距离其最近的 ![][image8] 篇论文之间的欧氏距离平均值。这种朴素距离测算的致命缺陷在于忽略了不同科学领域之间存在着巨大的知识密度差异。例如，在计算机视觉或大型语言模型等研究热点领域，文献在特征空间中的聚集程度堪比黑洞，导致任何该领域内的新想法，其绝对距离都显得极其短小；反之，在某些边缘的理论物理或冷门的生物医学分支，即使是一个极其平庸甚至毫无逻辑的拼凑之作，由于周围文献稀疏，其绝对距离也会异常惊人。这种不同领域密度的巨大方差，使得传统的距离算法在进行跨学科多域评估时彻底崩溃失效40。  
面对这一难题，RND巧妙地引入了“相对（Relative）”分布的度量理念。该算法首先精确定位待评估的生成想法 ![][image9] 在特征空间中的前 ![][image8] 个最近邻，并计算这群邻居构成的微观局部密度。最为关键的一步是，RND并非孤立看待这个密度绝对值，而是继续深挖，去分别计算这 ![][image8] 个相邻历史文献各自在其所属更广泛历史网络中的固有局部密度（即为每一个邻居寻找其自身的前 ![][image10] 个最近邻，以构建历史基准面）。在大量经验实证中，算法参数通常被优化配置为 ![][image11]40。  
最终，系统通过比较这两种密度的比值或相对排位来给出判决。其核心哲学逻辑十分清晰：如果待评估科研想法 ![][image9] 所在的区域，明显比该区域历史邻居群体曾经所处的基准区域更加稀疏空旷，这意味着该想法成功逃逸了现有的知识引力场，正在开辟前人未至的新领域，系统将赋予其极高的新颖性得分；反之，如果该想法不偏不倚地砸进了一个已知拥挤的科研“贫民窟”，那么无论大模型用多么华丽的辞藻包装，其新颖性得分都将跌入谷底40。  
RND算法的伟大与革命性在于其展现出了令人惊叹的**领域无关性（Domain-Agnostic）**。在横跨NeurIPS（代表计算机科学最前沿）与Nature Medicine（代表生物医学最高水平）两大领域混合测试集的苛刻验证下，RND算法在完全不依赖任何领域专家先验标注的情况下，依然能够提供一个单调递增、具有极强跨域普适可比性的新颖性量化评分39。其基准AUROC表现不仅将传统的历史相异度（HD）等非大模型算法远远甩在身后，更在统计学意义上全面碾压了包括最新版Claude与GPT-4在内的SOTA大模型裁判39。  
将RND算法作为科研论文自动生成Agent内部评估网络的最核心奖励函数——无论是用于评估MC-NEST演化树节点的前瞻价值，还是用于标定IDEAgent质量多样性计算中最大团的多样性权重，亦或是作为Nova锦标赛的首席客观裁判——都将从根源上重塑Agent的演进基因，彻底纠正系统“只图稳妥、不求创新”的保守倾向，为人工智能在无尽的科学探索前沿指明真正的北极星方向。

## **综合架构设计建议与结论**

科学研究是一项极其复杂的认知工程，大语言模型在AI for Science领域的应用正跨越从“熟练的代码复现者与文本缝合怪”向“拥有理论独创性的真正创新者”演进的深水区。当前科研自动生成Agent为了追求表面流程的跑通、零代码报错及虚假的语言流畅度，不可避免地陷入了迎合统计概率分布的平庸陷阱。  
本研究报告对当前在AI顶级会议与前沿预印本平台上涌现的旨在提升LLM科学发现新颖性的尖端技术进行了深度挖掘与系统重构。在实际开发并部署具备顶会级创新潜力的下一代AI科研科学家系统时，工程师与架构师必须摒弃依赖单一模型升级或简单RAG拼接的过时思路，转而构建一个深度融合长程知识规划、受控发散演化、多智能体协作网络和客观数学度量标准的复合生态架构。以下为整合各项前沿突破的系统设计建议：  
**第一，在文献知识摄取与底层拓扑构建阶段**，必须废除基于纯文本相似度的扁平化RAG架构。引入类似GoAI与SciAgents的大规模跨学科实体知识图谱，并通过Chain-of-Ideas (CoI)进行严格的时间序列演进建模。让智能体彻底理解一篇目标文献的前世今生，在厚重的学术史演进脉络中寻找逻辑支点，以此作为任何创新的底层基石。  
**第二，在受控的发散性构思阶段**，将科研方向探索定义为严格的IDEAgent质量-多样性（QD）搜索问题。在并发生成海量初始种群时，深度融合Denial Prompting（拒绝提示）技术。利用技术检测模块动态捕捉系统生成中的陈词滥调与常规套路，建立逆向约束黑名单，通过不断封锁舒适区，强制生成模块向高维、低概率但极具颠覆潜力的交叉创新解空间迁徙。  
**第三，在方案演化与路径探索阶段**，彻底淘汰单线直出生成模式，全面拥抱蒙特卡洛纳什均衡自完善树（MC-NEST）与智能体树搜索（Agentic Tree Search）。在假设空间中进行广度与深度兼备的节点展开，为每一个拓展节点配置具备专业化、异构化人格（Persona）的批评网络，通过极高强度的多智能体辩论与纳什均衡博弈，将每一个粗糙的设想打磨至逻辑闭环，从而在强硬保障科学可行性的同时挖掘极具深度的原创假设。  
**第四，在客观度量与终局裁决阶段**，坚决摒弃让语言模型“既当运动员又当裁判”的自闭环评估体系。在系统底层所有涉及价值判断的奖励回路中，全面部署具备领域无关特性的相对邻居密度（RND）算法。利用高维特征空间的相对拓扑分布，对科研方案的新颖性进行冷静且客观的历史尺度测量，最终在类似Nova的瑞士轮锦标赛排位中，洗刷掉所有的学术幻觉与伪创新，筛选出真正的帕累托最优（Pareto Optimal）科研硕果。  
通过将深度的逻辑链条组织、对抗性的反常规生成约束、树状多智能体博弈搜索规划，以及绝对客观的高维语义拓扑密度量化等跨领域顶尖技术进行有机的深度聚合，未来的AI自动化科研系统将不仅仅停留于以极低边际成本批量组装平庸论文的工业流水线。它将真正蜕变为具备无穷洞察力的科学先锋，在人类心智尚未触及的理论盲区与学科交汇点，持续提出具备深远历史创造力与革命性影响的伟大科学前沿突破。

#### **引用的著作**

> 1. HKUST-KnowComp/Awesome-LLM-Scientific-Discovery \- GitHub, [https\://github.com/HKUST-KnowComp/Awesome-LLM-Scientific-Discovery](https://github.com/HKUST-KnowComp/Awesome-LLM-Scientific-Discovery)  
> 2. The AI Scientist: Towards Fully Automated Open-Ended Scientific, [https\://sakana.ai/ai-scientist/](https://sakana.ai/ai-scientist/)  
> 3. (PDF) The AI Scientist: Towards Fully Automated Open-Ended, [https\://www\.researchgate.net/publication/383060918\_The\_AI\_Scientist\_Towards\_Fully\_Automated\_Open-Ended\_Scientific\_Discovery](https://www.researchgate.net/publication/383060918_The_AI_Scientist_Towards_Fully_Automated_Open-Ended_Scientific_Discovery)  
> 4. The AI Scientist: Towards Fully Automated Open-Ended Scientific, [https\://huggingface.co/papers/2408.06292](https://huggingface.co/papers/2408.06292)  
> 5. The AI Scientist: Towards Fully Automated Open-Ended Scientific, [https\://github.com/sakanaai/ai-scientist](https://github.com/sakanaai/ai-scientist)  
> 6. Evaluating Sakana's AI Scientist for Autonomous Research \- arXiv, [https\://arxiv.org/html/2502.14297v3](https://arxiv.org/html/2502.14297v3)  
> 7. \[2502.14297\] Evaluating Sakana's AI Scientist: Bold Claims, Mixed, [https\://arxiv.org/abs/2502.14297](https://arxiv.org/abs/2502.14297)  
> 8. Revolutionizing Research Via Novel Idea Development with LLM, [https\://aclanthology.org/2025.findings-emnlp.477.pdf](https://aclanthology.org/2025.findings-emnlp.477.pdf)  
> 9. arXiv:2407.09007v2 \[cs.CL\] 8 Feb 2025, [https\://arxiv.org/pdf/2407.09007](https://arxiv.org/pdf/2407.09007)  
> 10. An Agentic AI Scientific Community for Automated Neural Operator, [https\://arxiv.org/html/2607.12122v1](https://arxiv.org/html/2607.12122v1)  
> 11. Large Language Models for Scientific Idea Generation \- arXiv, [https\://arxiv.org/html/2511.07448v1](https://arxiv.org/html/2511.07448v1)  
> 12. 1 Introduction \- arXiv, [https\://arxiv.org/html/2603.19087v3](https://arxiv.org/html/2603.19087v3)  
> 13. Benchmarking Language Model Creativity: A Case Study on Code, [https\://arxiv.org/html/2407.09007v1](https://arxiv.org/html/2407.09007v1)  
> 14. \[2410.13185\] Chain of Ideas: Revolutionizing Research Via Novel, [https\://arxiv.org/abs/2410.13185](https://arxiv.org/abs/2410.13185)  
> 15. Revolutionizing Research in Novel Idea Development with LLM, [https\://arxiv.org/html/2410.13185v1](https://arxiv.org/html/2410.13185v1)  
> 16. Leveraging Knowledge Graphs and LLMs for AI Research Idea, [https\://arxiv.org/html/2503.08549v1](https://arxiv.org/html/2503.08549v1)  
> 17. Revolutionizing Research via Novel Idea Development with LLM, [https\://www\.qeios.com/read/AUB766](https://www.qeios.com/read/AUB766)  
> 18. IDEAgent: Agentic Quality-Diversity Search for Research Idea ... \- arXiv, [https\://arxiv.org/pdf/2607.22375](https://arxiv.org/pdf/2607.22375)  
> 19. Soumitra Sinhahajari | Semantic Scholar, [https\://www\.semanticscholar.org/author/Soumitra-Sinhahajari/2264628685](https://www.semanticscholar.org/author/Soumitra-Sinhahajari/2264628685)  
> 20. GitHub \- declare-lab/IDEAgent: Agentic Quality-Diversity Search for, [https\://github.com/declare-lab/IDEAgent](https://github.com/declare-lab/IDEAgent)  
> 21. IDEAgent: Agentic Quality-Diversity Search for Research Idea, [https\://www\.alphaxiv.org/abs/2607.22375](https://www.alphaxiv.org/abs/2607.22375)  
> 22. A Survey on Large Language Models in Scientific Discovery \- arXiv, [https\://arxiv.org/html/2505.13259v1](https://arxiv.org/html/2505.13259v1)  
> 23. Iterative Hypothesis Generation for Scientific Discovery with Monte, [https\://arxiv.org/abs/2503.19309](https://arxiv.org/abs/2503.19309)  
> 24. arXiv:2503.19309v1 \[cs.CL\] 25 Mar 2025, [https\://arxiv.org/pdf/2503.19309?](https://arxiv.org/pdf/2503.19309)  
> 25. The AI Scientist-v2 (sakanaai/ai-scientist-v2) | Context7, [https\://context7.com/sakanaai/ai-scientist-v2](https://context7.com/sakanaai/ai-scientist-v2)  
> 26. ResearchAgent: Iterative Research Idea Generation over Scientific, [https\://www\.alphaxiv.org/abs/2404.07738](https://www.alphaxiv.org/abs/2404.07738)  
> 27. Official Code Repository for ResearchAgent (NAACL 2025\) \- GitHub, [https\://github.com/JinheonBaek/ResearchAgent](https://github.com/JinheonBaek/ResearchAgent)  
> 28. Scientific Hypothesis Generation and Validation: Methods, Datasets, [https\://arxiv.org/html/2505.04651v1](https://arxiv.org/html/2505.04651v1)  
> 29. Innovation Discovery System for Networking Research \- arXiv, [https\://arxiv.org/html/2603.26496v1](https://arxiv.org/html/2603.26496v1)  
> 30. \[PDF\] Nova: An Iterative Planning and Search Approach to Enhance, [https\://www\.semanticscholar.org/paper/Nova%3A-An-Iterative-Planning-and-Search-Approach-to-Hu-Fu/2efae9851606b5f8b16edbbf357b30de5846876e](https://www.semanticscholar.org/paper/Nova%3A-An-Iterative-Planning-and-Search-Approach-to-Hu-Fu/2efae9851606b5f8b16edbbf357b30de5846876e)  
> 31. Nova: An Iterative Planning and Search Approach to Enhance, [https\://arxiv.org/html/2410.14255v2](https://arxiv.org/html/2410.14255v2)  
> 32. Enhancing Research Idea Generation through Combinatorial, [https\://issi2025.iiap.sci.am/wp-content/uploads/2025/07/22.-Chen\_fp\_issi2025\_187.pdf](https://issi2025.iiap.sci.am/wp-content/uploads/2025/07/22.-Chen_fp_issi2025_187.pdf)  
> 33. Improving Factuality and Reasoning in Language Models through, [https\://composable-models.github.io/llm\_debate/](https://composable-models.github.io/llm_debate/)  
> 34. HypER: Literature-grounded Hypothesis Generation and Distillation, [https\://arxiv.org/html/2506.12937v2](https://arxiv.org/html/2506.12937v2)  
> 35. SciAgents: Automating scientific discovery through multi-agent, [https\://www\.alphaxiv.org/abs/2409.05556](https://www.alphaxiv.org/abs/2409.05556)  
> 36. ResearchAgent: Iterative Research Idea Generation over Scientific, [https\://www\.microsoft.com/en-us/research/publication/researchagent-iterative-research-idea-generation-over-scientific-literature-with-large-language-models/](https://www.microsoft.com/en-us/research/publication/researchagent-iterative-research-idea-generation-over-scientific-literature-with-large-language-models/)  
> 37. An Axiomatic Benchmark for Evaluation of Scientific Novelty Metrics, [https\://www\.researchgate.net/publication/403905685\_An\_Axiomatic\_Benchmark\_for\_Evaluation\_of\_Scientific\_Novelty\_Metrics](https://www.researchgate.net/publication/403905685_An_Axiomatic_Benchmark_for_Evaluation_of_Scientific_Novelty_Metrics)  
> 38. Enabling AI Scientists to Recognize Innovation: A Domain-Agnostic, [https\://arxiv.org/abs/2503.01508](https://arxiv.org/abs/2503.01508)  
> 39. A Domain-Agnostic Algorithm for Assessing Novelty \- arXiv, [https\://arxiv.org/html/2503.01508v1](https://arxiv.org/html/2503.01508v1)  
> 40. A Domain-Agnostic Algorithm for Assessing Novelty \- arXiv, [https\://arxiv.org/pdf/2503.01508?](https://arxiv.org/pdf/2503.01508)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIsAAAAaCAYAAACHI68ZAAADSklEQVR4Xu2ZS6hNURjH/0J5PyISdWMiI8rAI4lSkkge5TkyoDxylYS8MxRKkomkjJQMSCiniKLIgIGSRx4hTJhQ+P9be3XWXvfss8+5Z59z9j7Wr365Z6/dvutbvvWtb58LBAKBQCAQCAQCgUAAWEO/0b+OP+hm96YOpYix74eZoztnxbDAvamZ9KHn6R+08JfmhCLGPoSW6Fc6JT7UfEbSR/Q1HR8f6niKGPsk+hEmYZQ4LWU6/Ukv037eWKdTxNiXwhw/x/yBVrAO5pfv9Af+A4oYu5JEc17kDzQbe2b/pnO8sU6niLHbfkXHkI6jlmLP7Jd0rDfW6RQxdtuv3KaDvbGmk8WZPZSeoy/oLToqPoyB9CJ9Tq/QifHhtpEUuyrOXHqU7qLDnLF2U61fWUsf0rd0uXN9L8zaa2yZc71usjqztUuVEI/pBG9MZ+sTVA6wnSTFrv+Qs7Q/nQETlxI+D6T1K/ruSGt9A+U5K/kPoMHqmeWZPZVup/dgdqyli66n95Gv7zGSYleFUaVZEn1Wj3Adja9PFqT1K4qpmy6mn+ms6Lo2sq5rvNdk+R3DCphsL6G80Fp4lcZ5MGWwUoA+2s1KMP2bhHaIf9S51PKMpNhH02eIJ0sJpgolkcV80p4h0r5f0dx1bKqiqLKchkkQbV5VnIZIOrN7wxaYyV5AuazPpNNgFvoaHRBdr8ZxmDJ7yLtumUw/0XdI7n3SniGSYh9H36Bnsuy2N3hkMZ9aniGq9StCMekesRqmd9HzdM2t9nWxgX5A/O8LKlsbnXvU4KlpreQZxL9m1i7dB7PoCkRql6yifWHKfVKAPjvoL5hKVQn1Q09h3gaGe2MW+wy7cC5psdebLPXMJy2mm6hcMY7AzNGdsxJrvnsTTIKoHRBafzW02+gemI2cC5Q4K6OfN9FL0ecxMImUt36lGnqzu4ueyeK+XeQR269ovS1b6St6OBrPBdoxtgHUIuuvoAujzyp/tfYreUCLqrPe9ijakXfQhj/Y1YntV1x0BKkCaQO3nRH0BP1Or8KcvUqOU3QQzNvRA/qFnkSDr24tpAumx5pNDyKDN4kmo+NW1fA94omhOev473W/EqgNvbkoubUhAoFAIBAItJ5/StjF8NPcg7cAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFAAAAAXCAYAAACcTMh5AAACRUlEQVR4Xu2YTUgVURiGv6jAhMgoaqHgz0aEwKBNiwgXQYXopgJ/atWiQBAVWrW5G5dRbly0CRFKIRGJVrVoESYISYtcCEKLCErIjW0M0vf1O3PvmcN17sScvJfpPPCgc75h7nznnvPOqEggEAgEAoHaoB/+hDuWW/C+fVJO8db7IfgM/oFXnFre8dL7SbgMv8DGeCn3eOn9AvwFX8IjTi3veOl9UHT/j7mF/4DMvUcZ8Btecmp5x0vvUQasw7NOLe946d1HBhyHT+EafANPxctyDE7DVTgPW+PlqpHUO3uYFe3pFTxhxtuLZxgyZ4CB3yYn6SNscmrX4Qocd8arTaXeT8MZ+B1ec2p7eMkAQycchu9Fv9mIZngbLkqG96x/QJre2ccN+MLorlI/70AGfhBX2jvYY8b4gQOwS3T7tpnxJI6KTjp/7gfzyo0JmzTXSNN7n+jC4OrjKjwnOvFFkjLgbxkSXfJTUtoSF+F50a3yGtaZ8SQeiW6rgjMewQxiM19l/yytdA1SqXdO1KjoRDP/lkSvx2O5A79J/G/AH/Aui4bLog+Gck7CjtKpexd9KHojzDnKFXILHhbdKmnzbwRui67ocjBfP8G3Ugp2l+gavW5B0vVOuBgeWMeMoc+w2xrzBifzpvn9Hnxujs+ITm6t5V8auELtL4CxwQnkW4R3uFqiIGb+8T8cV80xbyRt/tUSUf7ZFEQn0RsN8DHchAui+cQJm4D1ok/lD3ADPpEML6sHCKOH98qe5mCLVeNDhPkayMIuJ6+DBN2xV3gAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEEAAAAXCAYAAABUICKvAAADe0lEQVR4Xu2XWciMURjH/7JkzRqJbH03QhEpZbtAXFjiRpEbStZQKJRPkoiyliTLhVxwQShJmSKJEkrEp5BIkitlyfL/f8975nveM+/MOxdzY5p//ZqZ513OOc95ljNAQw011FC+upPOsbGO1JN0jI1eY8kZ2I31pPakP2yDJ5LzKLPGweQ2GRVf+I/VlVwkfxPmJPal5ASiiGhHDpFmb6wjbSMfyYjkdxdylSws3kGNJi+Sz3pTB3KJFGDpELSY3HO/sZVcR30WxEHkDTkS2RUVLeGHFi4HKGRiqaBMJuOT70LfZ5Fu7r48xe9R+g0jC5xN6kvmkqnIqeA5UtHTHPXuaeQHmZe6w+Z/K/wYSN7CBo+1HFYnHpKzsLBaT7aTJ2RouDFH68gu8hT2vuNkN1kG2w1dW01OwcL0CrmJdPhWIzluB2y+S2Dv+0C+kJHuvqBz4Yu89Qm2U179yGkyABYpL0lTcq0HuYPSEMuSnj8Me588/xXWpoI0kT9kMyxCJG3IN9jcqpWe3UJewaJMUmQ9Qmk9CFIZaJUGepd8eo0ha5CdU71h3tai8tJiAlkBa8HvyT60LTakYgHpSWpyvppXo0mwsG92tqy5e+U6IUgREueUQkshpkNHWFCeZpCfyWdQmOQeZwuOuQFrZdVKC/2FdERnzd2raidsQumuKN90+FjpbHmKe7Ukh/xGepJq00qZtc6WJ0VRgTyDpV2QFlmuHkhFJ2hSKh7hNOWV1WNlu0Cew0JcCsfSci027G6cPllhr8XLCXKGQnxjYq80RnCCf3+Yu2pXH7KfDEmuBRUjUJ6TB7N2NYTrfbSdtaeQz0ifttRFFBlyjgaPFepBVtj7iXcilxO7FnYQbRFaaQyl5DGkN2sRLMpUeIfDjsnegXpG6Vz8oT9NWcUj5JS8WYCdwx/Deq+Xqvl38hrWcmNpR7W7051NXUP3NzubtAFW4bWLq5DuGJXGkKM1Tz0nR+6FtcsWcg3pjiSpuD/wBvVmGXTBy+eUPKyWU64QystHYYuLpVDWu+Nny/2t7YXsllZpDCmkjH+23Lu0MUrporS4u2S2s2XVg0pSyB1AaajWUrUaQ5uhw5pISRVa4a62pN1RLqpgyibvhqNtlnRNk5sZX6ihajlGE6wWlZx45R2d2sQ4ctKxE5WjQTk6H6XhXkvVagxtsGpga2H/B2KHrhvnIkyuAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAbCAYAAABFuB6DAAAA5ElEQVR4XmNgGAWDG/ABsScQy0L53EDsBsTGQMwMU8QJxFOBuAqInwFxBxCvAeJoKD0LiFlBCl2AuBqINYH4LRDPgWoGAVMgfg9VQ7zCBCA2A2I/IP4LE4QCGyD+DcRFSGIMrUD8AIilkcTSgfg/EAfBBEC+3MMAcTwLVAxEg/gg54CcBQZKQPwciMthAkCgCMRPgHg6A0Iz2H0gKxqgfEYgbgbiK0AsDxUDA5D7QL47AcSrgfggA8RaCWRFPEB8AIi3MkCCRRgqhgGwuQ8rSGOAuC8OiAXQ5FAAKC5hOAJNbjAAADIoKc1zw8NaAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAaCAYAAAC6nQw6AAABFklEQVR4Xu3SMUtCURjG8TcyKCgjdJFoDQIhBwmCFreEiIjWoKkInBRxUKTP4Fa4tLcVEdEg+Akc2tVRkaAhCJf+rx4Pr1e/QHIf+OG9z+Ge6z3niIQJs8iJIosdd7+CNM5Mt4RdXLhfvZ/KOu5RRReXeMY1yujjBA+o4AptFCSQY9xgH9/4wKYbS6CDHg5cp3lEQ8Z/wudWxpOcY4iMGdvDACXT6cMNPCFiep8aPhE33Sl+cWS6yeQ50/lsoCmzb9HJ29g2nU7whaTpfCZvyZtu3ies4c3R66JMr51fn3mfYCfXbddd1M3RY1GXwILfoYWY6fRc/eDQdPrQK97xgpQZG2VVAjOTZWzJ7MHTXjdED22Yf50/FjQuGLp3KUoAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAZCAYAAADnstS2AAAA30lEQVR4XmNgGAUMPEAsBsTM6BLIwBGIfwLxfyDeA8TcqNKYQAaInwBxK7oENmDDADHdD10CGygH4rdArIkuAQIgT4AkfIFYHIjXAPEBBognUQBI0QUgbgfiNCj7FxBPQlYEAvJAfAuIK4GYESqWwAAJCRT3gkwEuQtkJQtUDERjdQLIfSAT0pHEpIH4AQMWJ8AUeyKJgYLsNxAHAbElEBfCJHQYIM6AuY2fARJjX4HYGIirgdgFKgf2UA4QXwTiuUC8G4gDgfgKEO8E4l4gZoUphgH0BANSIILEHwUoAAA9kSTPisEMJgAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEkAAAAaCAYAAAD7aXGFAAADv0lEQVR4Xu2YWchNURTH/zJkzBiJTHkRikiU6QHxYIgXRV6QjCFDoXySRJSxJBke5IEHQknKLZIooUR8CokkeVKGDP9/62zfPvvue+65uonb/dW/e791ztl7nbXXWnvfD6hTp06df5/2VOvQWEN0pFqGxkoYRp2ADVRLNKe6wxJgFHUaf/iOvanr1ODwwn9MW+os9TPRtMQ+nzqCCjOqGbWPagjstcIm6i01IPm7DXWRmv37jhwMoZ4kn7VGC+ocVYCVm2MudQsVlN1G6jJqs2H3ol5QBwK7sqqRGhvYoygwCpBSMkQNT4OMSL5L+j6FaufdV45wHJV3P2qWZxNdqenUeFTYLwKUHfJRY0+gvlAzUneY/9cQf+8ielIvYc6FLIT1qbvUSVjarqI2Uw+ovu7GMqyktlEPYeMdprZTC2CrqWvLqGOwMrhAXUW6PPKgwG6B+TsPNt4b6gM1yLvPcQq202nRMlG036E47bpRx6kesEx7Sg1MrnWgbqA4hWPo+f2w8bRyH2HbsEOO/qDWo8lZLdgnmG950bMbqGewLBXKzHso7kcOtZkC4tdSyJFXyafPUGo54jXdGbZaeulyZTeSWgQ7YrymdqEpGK7UC0g7Kuf93SgPY2Bl1eDZYr77aB69h94nk1JBcijDwppW6iqFc6VqwiTqa/LpcC+xw7O5wF2BbdV5USC+IV0RMd99FKTnsGzPpFyQ1qJ4VVXvOpwt8WzlCM8qQgH7jvRL6Biiklzh2cqhLCxQj2Bl7VAQSvUjkbvc5LSamzuN+sTOGLKdoR7DSki4Y3+pI4TLjrA8Y2Wl4ChICpZKaE1iz5rDBckf3/mu3tmF2k31Sa45lMGhT1EUea1ALCtcOdxG06FrHPUe6dOqdkFlloIn50JcP4qVle9kK+p8YteL70VThmfNoZI/hPRizoFlqTaG/rCfIX6A9YzaRal+lUI360dt7GZX01qNAux30H3Y2cNHu9FnWH3rSBGijFB2TPRs6gO6v8GzidWwHUpZsBTpHS9rDi2E/NRzCvRO2HGgkbqE9I4q1KzvoHS/KkJnEz0Qdnm/prVC2lJLNWqt0kHEm6BKRWOHz5b6t0UnxPtE1hzClaT/bKmxtHBqGcqyXOjlb1JTPVusH2WhyfaguBSqSbXm0GLpMCuFC5eJ0k7lpG1Xq6teoIYum1bH/XSIoWtyfnJ4oYpUc46BsF6Y9xfDbxRRnXql4dRRT1uRnU3qETNR4apUSLXmUAKoB1f0bxIfDbCOGh1eqCEWI91W6tT5C/wCu6y2FcvXaOwAAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAAA3klEQVR4XmNgGAWDDzgC8XMg/o+E3wHxKyj7CxBPAGI+mAZcYA4Q/wZiGzRxIwaIYbuAmAdNDg54gfgwEN8FYnE0OZCmA0D8D4hdUKUQQBOI3wLxGiBmQZMTBOLTDNhdBwd+DBD/FqFLAIElEP8E4hNAzI8mBweTGLDbANKwB4hfA7EJmhwcwPwIsmUpEM+C4oVA/AyI5wOxDEwxNgDz/24glgdiSSTMgaQOJ4D5vwpdglgA8j/eKMIHYPH/AIilUaWIAzpA/B6ItzIQ6V8YsAXihwyY6T8ZWdEoGNYAAJNrMDdrjbSbAAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAABEElEQVR4XmNgGAWjYDABZiA2BmI7IGaFijECsT4Qy8MU4QIgDb1AXArEJ6BsEABp/gTEe4CYGyqGFbgCcQ0QCzJADFgIFecE4gVAfACIeaBiWEEqEGsCsSUQfwPiCCQ5GyCejMTnB+JMKI0BGoD4CRArIokFAXE6Eh/krSkMWFwEcv5pIF4DxCxQMVAgNjBAXEcQSALxQyAuRxIDuaSHAWIgyLAAIN4GxAZIauBAHIjvAnEVlA+KmU4gNoTyQa7whMo3QMVQAMiGLCB+CcSLgHgHA8RGGBADYjkGiAtAAYsTcDBAvAOi0QEolnYz4IgBYsAkBkgYeQGxDpocUQCUQkFpIpcB4mWSAUgTL5QeTgAAOIMgyZGQ2MMAAAAASUVORK5CYII=>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAABT0lEQVR4Xu2TvytGURjHH2EQMhApo8WPRWGSwaDUa2MQFoOU0SCbksHAIKX8AyaDySZlkZkJoWRRTCaFz+M5h3vPPYd3scinPt17z/f0vOc95zki//w6jTiMY9iBlfk4TgUO4ike4KTzEC+x72tqkWpcw2spTtRsB5+wJ8g+0Anb+Ij9QebpFiuwJbbSHHP46p4pWvEWz7EpG7TjPZ5hczYI8AVUff9kGd/c8zva8E6CAnV4hC844AcTaK7zjrHeDyaXFWFRIiv1BXJVIzTgCT5gVzbQ3dRdvcKWbBAwJXZKC2FQhbti56vnrP2wItZ16+5b+0JzbST9LqCd5SdM4Lgbn8Z5vMENrHHjUbR1L8R2eVWs//fFVjIk1nl6maIr8GjYK3b7RnFWrJin5PKymcFnsY3bxD354W+EjIidu6p7lLpkSWpxSezXO4Psr/AOceY/xA0xYsUAAAAASUVORK5CYII=>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJQAAAAaCAYAAABRhnV8AAAFUElEQVR4Xu2aa6ilUxjHH6Fo3EfuckaikSkxTCOKXCKXZJBmPvggoxAlIaWUFKLwwQeJKLnkm1xCOiKJUoQpQw65hJAaSnL5/86zn2bttd/17nfPnrP34axf/Zs9723e91n/9axnrTVmlUqlUqlUKpVKpfI/YwfpIOl86UJppndsSXKa9J30T6KfpR96v7dI90t7xA1TYka6LD+YcJR0j/SwtF7atf/0PHzD9ebX3CYd2H96ZHaULpU+lR43f78rpI+kt83feVqski6R9jM3927SKdKG9KLeuTXSg9JD0rnm3zU2j0h/Sidnx48zN9cr5i81SVZKV0uvS3+ZN1oT66RPpGPN3/EO6VVpz+Saw6QPpCulXaRzzI1wYnLNKPDsp6V3bdA4nHtN2iQdkp2bFJg7TRLoK/MYBZjpJukNaYW0XHrSvMPtnFw3MrtLb0qfS/tn52igWelv6Yz+UwsOhmIIOUn62poNdai02fp73t7Se9K1vb/vZN5hnuv9Du6UXrbmbNYGhnnJ3JAYtYmzzWMW7zBpGH5pT/SOeWbOR5njpe+tP4kcLn1p/v7bDA33kw0GHKJxmrLXpGBo4iObDIWRfjMPTkDPo6fNmncIgsSwfnNyDVxkg/cOg2dTApAxz8zOpfBMnv2CeUacNBgq/94cOhRxTYf+SC6P2Rh14AXmKfGG/IRYK/1h7vJ0CJkkbYZi7G8yBddiIsxEZiVb5AEm6Hx3Xle0QR1CPJ639swWhpq1yZcKMMxQmByz54aKEYkkQjLZJmiUpgwUtcCP0urs3CRpMxTHSoaK42GcPMCl4yXI3k+Z39M2QYATpN9tuoYiBgzpDHtfmNePUXCHcUqGyo93Jh5Ar4uCDPEy35qnvi6FJbMmir6u4kP3mb9zOCVDxbsPMxSGaTLOqIY6WJqzrZmvDbIezyampaGD7ycOeWzaRJy7wLcxmYkYH2Feh1KE8z4R09w4Yxsq6idmRRSYPCQ0jbG/iZKhlpln0GGGYihvMs6ohuo6jNFgdMQumWyhoO3S9uOdMDemWmE++SJz5cYZ21BRP92an1hElAwFqXFKx0vGKR0vEYZqyzpAg9FwrEexDrRYICZ8L0smJeOUjneG+ml7LAnwIml2GyYC3XUBrc1QzFRKhqJRGa6pDakRc+OEoZjtdSGyOVmR7NgERmMdjFkgnbUNrl1ug7Fp017zd7ZzpPSNDU4cwlB8N/Ugs/rcOGEoZnrM+EYipohz5vXBOKySLh5B9JK2WVJKm6FoNBov7RAxg0H8jtqHzpNylblBMEpAg5UajUkKs91N5kMGf39U+ky6ztwg68zNG7VKGywenm6DsWnTmvk724lMmhqKdyGzpp2PDpZ//77SxzYYq04cI/1i01sr6UoYqmmooYezWn17ciwK0KhfImukSx805rPms7ZYe2P7hoW+qDOawMBhmBvNG5jn3yJdY95ALCJ2zb4LAd9IrGaSY/ymZkpXwfM4Acsi7IysTY4NhZtoINJfiP079qEWE2QdPpgMFO+5RfrQPCMGq82nxTQyvZg1lLutf/uAIL8oPWOeHcksb1n/DJbfbM9QAjAsNIF5zjM3zq/mpiJumBVjH927DpOGUacBMXnfvDYme86ZbxXla4kM98Ruo3S5+RYW2115x11yUNOcZb5Vw3ZME2QN0j2m489SFmG9BtO1QUY/1fxZ/Lt32dYFUhqDxilluUmRxmTGyiYhy9OBEL8r2xGyyr02uhnuM18nonc/IT1g5QasLCHYFGW4HNUMsdaF2jaNK0sIshP/vymvM7pwgPkSBuqys1CpVCqVSuW/xb+7glAMJbSfDAAAAABJRU5ErkJggg==>