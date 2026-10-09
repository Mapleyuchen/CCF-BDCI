# 未知论文

# International Conference on Learning Representations (ICLR) 论文评审报告

## 核心贡献

**核心贡献总结**

本文研究的是**语言模型代理中基于检索的记忆系统与基于文件前缀的记忆系统在准确率、证据完整性与构建成本方面的对比分析**。研究聚焦于记忆选择机制的有效性与成本效率，旨在揭示在不同资源预算下，记忆系统的设计如何影响模型的推理表现和实际部署成本。

首先，论文提出了**两个互补的研究设计**，分别从操作层面和控制层面评估记忆系统的性能。在操作比较中，作者在匹配字符预算的前提下，对比了基于文件前缀的记忆系统（file-prefix memory）与基于检索的运行时记忆系统（retrieved working memory）的性能。结果显示，检索记忆在受限预算（600字符）下将准确率从0.0%提升至65.0%，在扩展预算（2400字符）下从60.0%提升至95.0%。然而，由于检索记忆依赖模型生成记忆项，其构建成本显著高于文件前缀系统，分别达到21.70倍和15.64倍。这一发现表明，**虽然检索记忆在准确率上有明显优势，但其高昂的构建成本可能限制其在实际系统中的可行性**。

其次，论文在控制比较中进一步**隔离了记忆选择器的行为**，通过固定候选记忆库、打包策略和预算，仅改变排序规则。研究发现，部署的混合排序器（hybrid scorer）在所有预算下均显著劣于BM25基线，其准确率差距在512、1024和2048 token预算下分别为36.1、29.4和33.7个百分点。进一步分析表明，**混合排序器中固定的时间衰减权重（temporal term）是导致性能下降的主要原因**，移除该权重后，其在1024 token预算下的准确率提升了27.0个百分点。这一结果揭示了混合排序器在设计上的局限性，即**固定的时间衰减权重可能掩盖了更相关的旧记忆项**，从而影响了整体检索效果。

从方法上看，论文采用了**严格的实验设计与统计分析方法**，包括分层抽样、配对聚类引导区间（cluster-bootstrap intervals）和Holm校正的显著性检验，确保了实验结果的可解释性和稳健性。此外，作者提供了**详尽的审计协议与数据处理流程**，包括对每个问题的独立记忆片段处理、查询与写入的分离计费、以及对模型调用的完整记录，这些都增强了研究的透明度和可复现性。

该工作与**表征学习与深度学习领域密切相关**。一方面，它探讨了如何通过记忆系统的设计优化模型的推理能力，这与表征学习中对长期记忆建模的研究方向一致；另一方面，论文强调了**检索机制在信息选择中的作用**，并揭示了混合排序器在实际部署中的性能缺陷，这为未来设计更高效、可解释的记忆选择器提供了实证依据。此外，论文对**模型调用成本的量化分析**，也呼应了当前深度学习系统研究中对计算资源与模型行为之间权衡的关注。

综上所述，本文的核心贡献包括：（1）提出了操作与控制两种互补的记忆系统比较方法，揭示了检索记忆在准确率上的优势与构建成本的代价；（2）通过控制实验发现混合排序器在记忆选择上的性能缺陷，指出时间衰减权重是主要瓶颈；（3）提供了详尽的实验设计与审计流程，增强了研究的可复现性与透明度。这些贡献为理解记忆系统在语言模型代理中的作用提供了重要的实证视角。

## 研究动机

从研究动机来看，本文提出了一个在**多智能体系统中如何有效利用记忆**的科学问题，具体聚焦于**检索式记忆与文件前缀记忆在准确性和构建成本上的对比**。作者明确指出，当前许多基于语言模型的智能体在使用记忆时，往往仅关注查询阶段的性能，而忽略了记忆构建过程中的模型调用成本。这一问题具有明确的研究边界和可操作性，符合ICLR对**学习表征**和**系统行为分析**的关注点，尤其是对**记忆选择机制**的深入探讨，体现了对模型行为和资源分配的系统性理解。

研究动机部分充分说明了当前智能体记忆系统中存在的重要问题：**文件前缀记忆虽然构建成本低，但容易丢失关键信息**；而**检索式记忆虽然理论上能提供更完整的上下文，但其构建成本可能被低估**。作者进一步指出，**仅与弱基线对比可能高估检索系统的实际效果**，这为研究设计提供了合理的理论依据。此外，作者强调了**时间衰减项在混合排序中的负面影响**，并提出需要将**排序规则与记忆构建过程分离**进行评估，这一动机与当前深度学习系统中对模型行为的可解释性和可复现性的重视高度契合。

该问题在**表征学习与深度学习领域内具有较高的迫切性和重要性**。随着语言模型在复杂任务中的广泛应用，如何在有限的上下文预算下高效地管理记忆，已成为提升模型性能和系统效率的关键挑战。本文通过**严格的系统审计和控制实验**，揭示了混合排序规则在实际部署中的局限性，这不仅对智能体系统的优化具有指导意义，也为**检索增强生成（RAG）**和**长期记忆建模**提供了新的视角。例如，作者指出**时间衰减项在混合排序中可能掩盖了词法相关性的优势**，这一发现对设计更合理的记忆选择机制具有启发性。

从与ICLR主题范围的匹配度来看，本文的研究内容高度契合**学习表征**的核心议题。它不仅关注模型如何从记忆中检索信息，还深入分析了**记忆选择机制对最终输出的影响**，并通过**可复现的实验设计**验证了不同选择策略的性能差异。此外，作者强调了**系统层面的资源分配和成本核算**，这与ICLR近年来对**模型行为分析、系统效率和可解释性**的重视方向一致。尽管本文没有提出新的算法或模型，但其对现有系统行为的深入剖析和对实验设计的严谨控制，体现了对表征学习中**系统层面问题**的深刻理解。

综上所述，本文的研究动机清晰、问题定义合理，且与ICLR关注的**表征学习与系统行为分析**高度契合。建议作者在后续版本中进一步探讨**混合排序规则在不同任务类型中的表现差异**，并考虑**引入语义嵌入模型**以扩展实验范围，从而增强研究的广度与深度。

## 技术方法

在技术方法层面，本文提出了一种基于检索的混合记忆选择机制，并通过两个互补的实验设计对其进行了系统性评估。论文的核心方法围绕 **JiuwenSwarm** 系统展开，分别比较了基于文件前缀的记忆（file-prefix memory）与基于检索的工作记忆（retrieved working memory）在问答任务中的表现。作者通过 **ProjectMemoryRail** 和 **EnhancedMemoryRail** 两条路径，分别实现了两种记忆系统的构造与使用。EnhancedMemoryRail 将用户与助手的对话历史存储为独立的记忆项，并通过一个混合评分函数进行排序，该函数结合了 **Jaccard 重叠度**、**时间衰减（recency）**、**访问频率（access frequency）** 和 **重要性权重（importance score）**，其默认权重为 (0.4, 0.3, 0.2, 0.1)。这一评分函数的设计体现了对记忆项相关性与时效性的综合考量，具有一定的实用性。

从创新性角度来看，本文并未提出全新的表示学习方法或深度学习模型结构，而是对现有记忆系统的实现与评估方式进行了系统性的审计与比较。因此，其创新性更偏向于 **实验设计与系统评估方法**，而非模型本身的突破。论文强调了在评估记忆系统时，**必须同时考虑构造成本与选择器质量**，并提出了 **冻结候选库** 与 **固定打包策略** 的控制实验设计，以排除其他变量对结果的干扰。这种设计思路在当前对记忆系统进行公平比较的研究中具有一定的启发意义，尤其是在 ICLR 强调 **可复现性与严谨性** 的背景下，作者对实验细节的详细描述（如 token 预算、打包策略、评分函数等）值得肯定。

然而，本文的创新程度应被归类为 **增量改进** 而非 **颠覆性创新**。其核心贡献在于揭示了当前混合记忆选择器在某些场景下可能不如简单的 BM25 基线，尤其是在时间衰减权重固定的情况下，可能导致较新的但不相关的内容覆盖较旧但更相关的内容。这一发现虽然具有一定的理论价值，但并未对深度学习或表示学习的底层机制提出新的见解。此外，论文并未引入新的表示学习模型或训练范式，而是基于现有的语言模型（如 Qwen3）进行实验，因此其对 **深度学习前沿的推进作用有限**。

在方法设计的合理性方面，作者采用了 **严格的控制变量策略**，确保在比较不同选择器时，仅改变排序规则，而保持候选库、打包策略、token 预算等不变。这种设计有助于明确评估排序机制本身的效果，避免了传统实验中常见的 **基线选择偏差** 问题。此外，作者对 **成本分解**（包括查询与写入的 token 使用）进行了详细记录，并通过 **配对聚类引导区间（paired cluster bootstrap intervals）** 与 **Holm 校正的统计检验** 来增强结果的可信度。这些方法在 ICLR 的标准下是合理且严谨的，体现了对实验可解释性的重视。

然而，本文也存在一些潜在的技术风险与计算壁垒。首先，**混合选择器的写入成本显著高于基线**，在受限预算下是其 21.7 倍，在扩展预算下为 15.64 倍。这种成本差异可能限制其在实际部署中的可行性，尤其是在大规模问答系统中。其次，**时间衰减项的负面影响被明确指出**，但作者并未进一步探讨如何动态调整该权重以适应不同任务或上下文，这可能限制了方法的泛化能力。此外，尽管作者强调了 **证据交付与答案正确性之间的强相关性**，但并未提供对模型内部推理过程的深入分析或可视化，这在 ICLR 对 **模型行为分析** 的要求下略显不足。

综上所述，本文在 **系统评估方法** 上具有一定的贡献，尤其是在揭示混合记忆选择器的局限性方面。然而，其在 **表示学习与深度学习理论层面的创新性较弱**，且实验设计虽严谨，但缺乏对模型内部机制的深入探索。建议作者在后续工作中，尝试引入 **动态权重调整机制** 或 **基于学习的嵌入表示**，以提升记忆选择的灵活性与泛化能力，并进一步提供 **模型行为的可视化分析**，以增强论文的理论深度与 ICLR 的评审标准契合度。

## 实验验证

从实验验证来看，本文对记忆选择机制进行了系统性的对比研究，分别通过**操作性比较**和**控制性选择器研究**两个互补设计，评估了基于文件前缀的记忆与基于检索的记忆在准确性和成本上的差异。实验设计具有一定的严谨性，但存在一些可改进之处，尤其是在消融实验的完整性、统计显著性的解释以及实验可复现性方面。

首先，论文对比了多个Baseline和评估指标。在操作性比较中，Baseline是**文件前缀记忆（file-prefix memory）**，而增强臂是**检索工作记忆（retrieved working memory）**。评估指标包括**答案准确率（answer accuracy）**、**完整证据召回率（complete evidence recall）**、**查询和写入的token总数**、**查询延迟**和**端到端延迟**。在控制性选择器研究中，论文进一步对比了六种选择器：**prefix（无排序）**、**recency（仅时间衰减）**、**jaccard（仅Jaccard重叠）**、**hybrid（混合排序）**、**hybrid_no_time（去时间衰减的混合排序）**和**BM25（标准词法排序）**。这些选择器在相同的**冻结候选库**、**元数据**、**打包策略**和**token预算**下进行比较，确保了实验设计的公平性。然而，**BM25作为词法基线的合理性值得进一步讨论**，因为其在实际系统中可能并不作为默认选择器，而本文的混合排序在多个预算下表现明显劣于BM25，这说明当前的混合排序设计存在关键问题。

其次，论文在控制性研究中进行了**关键的消融实验**，例如移除时间衰减项（hybrid_no_time），并观察其对结果的影响。这一实验揭示了时间衰减项是导致混合排序表现不佳的主要原因，具有一定的洞察力。然而，**缺乏对其他关键组件的独立消融分析**，例如访问频率（access frequency）和重要性权重（importance score）的单独影响，这限制了对模型行为的深入理解。此外，**未提供关于不同token预算对选择器行为的系统性分析**，尽管论文提到了三个不同的token预算（512、1024、2048），但并未明确说明这些预算如何影响不同选择器的性能差异，也未提供跨预算的综合比较。

在统计显著性方面，论文使用了**分层配对记忆聚类引导区间（stratified paired memory-cluster bootstrap intervals）**和**配对聚类符号翻转检验（paired cluster sign-flip tests）**，并进行了**Holm校正**，以控制多重比较的假阳性风险。这些方法在统计上是合理的，且论文明确报告了**p值**和**置信区间**，例如在1024 token预算下，混合排序与BM25的准确率差异为-29.4个百分点，p值为0.0022（校正后为0.0022），具有统计显著性。然而，**论文未对所有非显著结果进行深入解释**，例如Jaccard与BM25在1024和2048 token预算下的差异不显著，但其表现接近，这可能暗示Jaccard在某些场景下具有与BM25相当的潜力，值得进一步探讨。此外，**论文未提供关于样本量是否足够支持统计结论的讨论**，尽管使用了10,000次重采样，但样本量（84个记忆片段）是否足够稳健仍需说明。

关于实验的可复现性，论文在方法部分提供了较为详细的**实现协议**，包括**冻结候选库**、**固定的打包策略**、**token预算**和**评分函数的权重分配**。然而，**代码和超参数并未公开**，这与ICLR强调的**开放评审和可复现性**原则不符。论文中提到的模型（如qwen-plus、qwen3-max）和具体实现细节（如Jaccard计算方式、时间衰减函数）虽然有描述，但**缺乏代码链接或超参数配置表**，使得外部研究者难以复现实验。此外，**未说明实验运行环境**（如硬件配置、模型版本、API调用限制等），这可能影响结果的可复现性。

最后，论文在**结果分析上较为全面**，不仅报告了准确率和召回率，还通过**问题级别的审计矩阵**展示了答案正确性与证据完整性的对应关系。这种**细粒度的诊断分析**有助于理解模型行为，符合ICLR对**深入分析和可视化**的要求。然而，**缺乏对失败案例的深入分析**，例如在混合排序中为何某些记忆片段被错误地排除，而BM25却能正确召回，这可能有助于进一步优化排序规则。

综上所述，本文的实验设计在对比研究和统计处理方面较为严谨，但**在消融实验的完整性、统计显著性的解释深度以及代码和实验细节的公开程度上仍有提升空间**。建议作者在后续版本中补充相关消融实验、提供代码和超参数配置，并更详细地解释统计结果的意义，以增强研究的可复现性和说服力。

## 优点分析

综合以上分析，本文的主要优点如下：

**1. 方法设计具有清晰的对比结构，有助于理解记忆选择机制的性能与成本权衡**  
本文通过两个互补的研究设计，系统地评估了基于文件前缀的记忆系统与基于检索的记忆系统在问答任务中的表现差异。在操作性研究中，作者在相同的字符预算下，分别测试了两种记忆构建方式对答案准确率和总模型成本的影响。而在受控选择器研究中，作者固定了记忆库、元数据、打包策略和预算，仅改变排序规则，从而能够将性能差异归因于排序机制本身。这种设计严格遵循了 ICLR 对表示学习研究中“方法创新性”的要求，即通过结构化实验揭示系统行为的内在机制。论文中明确指出：“The two studies together show that a memory benefit observed under a truncated-file baseline does not license a claim that the hybrid ranking itself is the better selector”，这表明作者对实验设计的局限性有深刻理解，并通过对比研究揭示了记忆选择器的真实性能。

**2. 实验具有高度的可复现性，并提供了详尽的审计与成本分解**  
本文在实验设计中强调了可审计性与可复现性。作者使用了固定的模型版本（qwen-plus-2025-12-01）、明确的字符预算（600 和 2400 字符）、一致的提示模板，并且在受控研究中采用了分层抽样和固定种子的机制，确保实验结果的可复现性。此外，作者详细记录了每条问题的查询与写入成本，包括模型调用次数、令牌使用量和延迟时间，并通过 Wilson 区间和 cluster-bootstrap 方法进行统计分析。例如，作者指出：“The cost estimand includes initialization through model-backed memory writes”，并提供了每条问题的总令牌数与延迟数据。这种对实验细节的透明处理完全符合 ICLR 对“实验的可复现性与严谨性”的高标准，使得其他研究者可以基于相同设置进行验证与扩展。

**3. 提供了对混合排序规则的深入分析，揭示了时间衰减项的负面影响**  
本文的一个重要贡献是通过受控实验揭示了混合排序规则中时间衰减项（temporal term）的负面影响。作者发现，移除时间衰减项后，混合排序器的性能显著提升，例如在 1024 令牌预算下，准确率提升了 27.0 个百分点。这一发现表明，固定的时间权重可能在某些情况下削弱了语义相关性的作用，从而导致相关但较旧的记忆被排除。作者通过“score-level analysis”明确了这一机制：“a fixed, query-independent freshness weight can outweigh a positive lexical relevance gap, displacing relevant older history”。这种对排序机制的细粒度分析符合 ICLR 对“深度学习前沿关联性”的要求，即通过实证研究推动对模型行为的理解，并为未来设计更有效的检索排序机制提供了理论依据。

**4. 对社会影响进行了审慎讨论，强调了实验设计的局限性与实际部署的考量**  
尽管本文并未提出新的检索算法，但作者在“Broader Impact”部分明确指出，实验结果不能直接推广到实际部署场景。例如，作者强调：“The two studies together show that a memory benefit observed under a truncated-file baseline does not license a claim that the hybrid ranking itself is the better selector”，并指出实验中未测试多会话推理、未验证端到端的论文生成流程，也未与已发布的记忆系统进行系统级比较。这种对实验范围的诚实描述和对实际部署成本的量化分析，体现了作者对研究社会影响的审慎态度，符合 ICLR 对“社会影响讨论”的要求，有助于读者正确理解研究的适用边界。

综上所述，本文在方法设计、实验严谨性、机制分析和社会影响讨论方面均表现出色，是一篇具有高度可复现性和理论深度的系统性研究，符合 ICLR 对表示学习与深度学习研究的高标准。

## 不足建议

尽管本文有上述优点，但仍存在以下主要不足：

**1. 方法创新性不足，缺乏对表示学习的深刻洞见**  
本文的核心贡献在于对两种记忆系统（文件前缀与检索型工作记忆）的系统性比较，以及对混合排序规则的可控实验分析。然而，论文并未提出新的表示学习方法或对深度学习模型中表示机制的生成、演化或利用方式提供新的理论洞见。例如，文中提到“**Neither arm employs learned embeddings, reflection modules, or external tools**”（第3.2节），这表明作者并未探索如何通过学习表征来提升记忆选择的效率或效果。因此，本文在表示学习的创新性方面存在明显短板。  
**改进建议**：建议作者在后续工作中引入基于学习的嵌入模型（如对比学习、语义检索等），并探讨其在记忆选择中的作用。此外，可以进一步分析不同表示方式（如词袋、TF-IDF、语义向量）对记忆系统性能的影响，从而为表示学习提供更深入的实证支持。

**2. 实验设计对模型行为的分析不够深入，缺乏可视化支持**  
尽管作者在两个实验中对记忆选择器的行为进行了统计分析，但对模型行为的解释仍停留在表面。例如，在第6.1节中，作者指出“**The deficit is large, consistent in sign across every budget**”，但未进一步分析为何混合排序规则在所有预算下均表现不佳，也未提供任何可视化手段（如注意力热图、排序权重分布图）来辅助解释模型内部的决策机制。  
**改进建议**：建议作者补充对排序规则中各组件（如Jaccard重叠、时间衰减、访问频率）的贡献度分析，并通过可视化手段展示不同选择器在不同预算下的记忆选择分布。这将有助于读者更直观地理解模型行为，并增强论文的解释力。

**3. 实验的可复现性描述不够完整，部分关键参数未公开**  
论文强调了实验的可复现性，但在方法部分对参数设置的描述较为简略。例如，文中提到“**The formalization below gives the audited default weights and normalization**”（第3.2节），但并未明确说明这些权重是如何确定的，也未提供完整的代码实现细节。此外，虽然作者提到使用了Qwen3的BPE分词器，但未说明其具体版本或参数配置，这可能影响其他研究者复现实验。  
**改进建议**：建议作者在附录中详细列出所有默认参数的设定依据，并在OpenReview提交时提供完整的代码仓库链接，包括分词器、排序函数、打包策略等模块的实现细节。此外，应明确说明实验中使用的模型版本、API调用方式及环境配置，以确保实验的可复现性。

**4. 社会影响讨论缺失，未评估系统在隐私、公平性等方面的影响**  
尽管本文聚焦于记忆系统的效率与准确性，但未对系统可能带来的社会影响进行讨论。例如，文中提到“**privacy analyses reveal new attack surfaces in memory stores**”（第2.4节），但并未进一步探讨该系统在隐私保护、数据安全或公平性方面的潜在问题。在ICLR强调社会影响的背景下，这一部分的缺失是明显的。  
**改进建议**：建议作者在结论部分增加对系统潜在社会影响的讨论，包括但不限于数据存储的安全性、记忆选择可能引入的偏差、以及在多代理系统中共享记忆可能带来的隐私风险。这将有助于提升论文的全面性与责任感。

综上所述，本文在系统性实验设计与成本分析方面表现出色，但在表示学习的创新性、模型行为的深入分析、实验可复现性以及社会影响讨论方面存在不足。建议作者在后续工作中补充相关研究内容，以更好地满足ICLR的评审标准。

## 总体评审

**总结**：  
本文对JiuwenSwarm系统中两种记忆选择机制进行了系统性比较研究，分别从操作性对比和控制性对比两个角度出发，探讨了检索记忆在准确性、证据覆盖和构建成本方面的表现。研究发现，在字符预算受限的情况下，检索记忆显著提升了回答准确率，但其构建成本远高于基线方法。然而，在控制性实验中，部署的混合排序机制在多个预算条件下均劣于BM25基线，且其时间衰减项是性能下降的主要原因。这些发现揭示了混合排序机制在实际部署中的局限性，并强调了在评估记忆系统时需区分构建成本与选择器质量。尽管研究设计严谨、实验结果清晰，但其贡献主要集中在系统评估和方法比较，缺乏对新算法或理论的实质性推进。因此，本文在技术合理性、清晰度和可复现性方面表现良好，但在贡献度和新颖性方面略显不足。

**评分**：

| 评分维度 | 分数（10分制） | 简要理由 |
| --- | --- | --- |
| 总体评分 | 6分 | 本文提供了对记忆选择机制的系统性评估，但缺乏对新方法的提出或理论创新，整体贡献有限。 |
| 新颖性 | 5分 | 研究聚焦于现有系统的评估而非提出新算法，虽然揭示了混合排序的局限性，但创新性不足。 |
| 技术质量 | 8分 | 实验设计严谨，控制变量清晰，统计方法合理，且提供了详尽的审计流程和结果分析。 |
| 清晰度 | 8分 | 论文结构清晰，研究问题明确，结果呈现方式直观，便于读者理解实验设计与结论。 |
| 置信度 | 7分 | 作者提供了详尽的实验细节和统计分析，但未进行多次独立运行或跨模型验证，影响了结果的泛化性。 |

**详细评审意见**：

**总体评分（6分）**：  
本文在系统评估和实验设计方面表现出色，但其主要贡献是对现有实现的审计和比较，而非提出新的记忆检索算法或理论框架。因此，尽管其研究具有实用价值，但整体创新性和理论深度不足以达到ICLR对高贡献论文的要求。

**新颖性（5分）**：  
研究的核心在于揭示混合排序机制在特定设置下的性能劣势，而非提出新的方法。虽然这种“负结果”在系统研究中具有一定价值，但其新颖性有限，未能推动记忆系统设计的前沿进展。此外，所用的混合排序机制和BM25基线在相关工作中已有广泛讨论，缺乏突破性。

**技术质量（8分）**：  
论文在实验设计、数据处理和统计分析方面表现出较高的技术水准。操作性对比与控制性对比的设计互补，能够有效区分构建成本与选择器性能。作者使用了cluster-bootstrap和Holm校正等方法，确保了统计结论的稳健性。此外，论文对实验流程进行了详细描述，便于他人理解其实验逻辑。

**清晰度（8分）**：  
论文结构清晰，研究问题明确，实验结果以表格和图表形式直观呈现。各部分逻辑连贯，术语使用规范，且在摘要和引言中对研究动机和主要发现进行了简明扼要的总结。尽管部分实验细节较为复杂，但作者通过分章节逐步展开，使读者能够顺畅理解。

**置信度（7分）**：  
作者提供了详尽的实验记录和审计流程，包括对每条问题的独立处理、写入和查询的token统计，以及延迟测量。然而，论文仅报告了单次运行的结果，未提供多次重复实验或跨模型验证，这在一定程度上削弱了结果的统计置信度。此外，部分指标如“end-to-end latency”仅作为会计总和，而非实际运行时间，也影响了结果的解释力。

**建议**：  
本文适合作为系统评估类研究的参考，尤其在探讨混合排序机制与传统基线的性能差异方面提供了有价值的实证数据。建议作者在后续工作中尝试提出新的记忆选择算法或优化策略，以提升研究的理论贡献。此外，增加跨模型或跨任务的实验验证，将有助于增强结果的泛化性和置信度。

Feedback:
Weaknesses
Technical limitations or concerns
The operational study’s comparison is anchored to an intentionally weak file-prefix baseline with deterministic truncation; while this is disclosed, it limits the generality of the “retrieved memory helps” finding and risks over-attributing gains to retrieval rather than to avoiding an obviously suboptimal policy.
The hybrid scorer’s coefficients and half-life are fixed heuristics; the study stops short of exploring whether simple tuning or per-domain calibration mitigates the large deficits.
Use of character budgets in the operational study vs. token budgets elsewhere introduces an avoidable confound and reduces comparability.
Experimental gaps or methodological issues
The operational study uses only 20 questions and single recorded runs without paired significance testing; it reports string-match grading, while the controlled study uses an LLM semantic judge—this metric mismatch further complicates cross-study synthesis.
Cost comparisons count model-backed seeding for the retrieved arm but not for the file baseline (which writes facts directly); though motivated, this setup under-explores amortization scenarios (e.g., multi-session reuse, caching) where construction costs could be shared or reduced.
The packing policy (whole-item, first-fit) is fixed and potentially suboptimal; no ablation examines whether improved packing (e.g., budget-aware submodular packers) changes selector outcomes.
The controlled study does not include modern embedding or learned hybrid retrievers; the principal comparison is with BM25 and Jaccard, which may understate how a well-engineered hybrid would behave.
Clarity or presentation issues
Some artifacts from PDF extraction (tables with stray indices) mildly distract; they do not impede understanding but could be cleaned.
The interplay between evidence recall definitions across the two studies (complete evidence vs. various sweep metrics) is complex; a brief harmonization paragraph would help readers map metrics.
Missing related work or comparisons
Limited engagement with recent system-level, cost-aware memory evaluations (e.g., MERIT), selection/packing literature (e.g., budgeted submodular packers), and multi-substrate memory comparisons and routing studies; the paper would benefit from positioning its findings within those emerging frameworks.
No comparison against representative learned or production hybrid rankers; at minimum, a pointer to why such comparisons were out of scope would be useful.

Technical soundness evaluation
The isolation of variables in the controlled study is strong: a shared frozen bank, identical segmentation, identical packing, and matched budgets attribute differences cleanly to ranking rules. The negative result against BM25 with Holm-corrected significance is compelling. The mechanism analysis—query-independent time weight overpowering lexical gaps—is a plausible failure mode consistent with IR literature.
The operational study is an honest audit of a particular pairing and estimand, but it conflates several factors (construction format, ordering, and formatting overhead). The authors correctly warn against overgeneralizing and avoid significance claims.
Using character budgets rather than tokens for the operational arm is a minor technical blemish; tokenization effects can be material in LLM prompting.
Experimental evaluation assessment
Positive: sound statistical handling in the controlled study (cluster bootstrap, paired sign-flip, Holm correction), budget sweeps, and retrieval-only sweep that strengthens interpretation. The per-question audit linking correctness to full-evidence delivery is insightful and matches known “answer-in-context” predictors of QA success.
Gaps: small N and single-run protocol in the operational study; heterogeneity of grading (string match vs. LLM judge) across studies; no sensitivity analysis for the temporal half-life or weights; no exploration of amortization (e.g., reuse of seeded items over many queries).
Additional analyses that would add value: (1) sensitivity curves for α (time weight) and half-life h; (2) replacing first-fit packing with a budget-aware packer (cf. budgeted submodular selection) to decouple selection vs. packing losses; (3) simple learned-to-rank or BM25F controls to test whether hybrid deficits persist when weights are trained.
Comparison with related work (using the summaries provided)
Relative to LongMemEval (2410.10813), this paper focuses on a narrower slice and modifies the protocol (frozen bank, segmentation), but aligns with the benchmark’s finding that session/round granularity and lexical baselines are strong when answers are stated verbatim. The evidence-delivery linkage mirrors the benchmark’s emphasis on retrieval-stage metrics.
MERIT (2609.05441) stresses cost-aware, leak-verified end-task utility and introduces explicit memory-injection metrics (e.g., CAMU). This paper’s cost decomposition echoes that ethos, but doesn’t leverage MERIT-style leak checks or utilization metrics (e.g., “ignore rate”), which would solidify claims about delivered-evidence utility.
The substrate comparison work (2608.15008) highlights regime-dependent routing and that broader structural/graph substrates can outperform simple retrieval on certain tasks. The present paper’s negative result for a naive hybrid scorer is complementary evidence that selection details matter more than “hybrid” labels; integrating substrate routing or task-aware policies could be a logical next step.
AdaMem, REMem, and ElasticMem (2603.16496, 2602.13530, 2605.30690) propose sophisticated memory organizations and retrieval policies. While this paper does not attempt to compete algorithmically, acknowledging these approaches would help contextualize why a minimal hybrid can underperform and what principled designs (e.g., adaptive/time-aware but query-conditioned) might avoid the reported pitfall.
The packing work (2607.00725) shows that placing answer spans into context under a budget is often the binding factor; this paper’s whole-item first-fit policy is a known heuristic and may leave performance on the table. A brief empirical check with a budget-aware packer could clarify whether the hybrid’s deficit persists when packing is strengthened.
Discussion of broader impact and significance
Practically important takeaways: (1) Accounting must include construction writes; query-only savings can be illusory; (2) naive time-decay in ranking can harm retrieval—designers should ensure recency is query-conditional or bounded so it cannot eclipse relevance; (3) evidence-in-prompt correlates tightly with correctness, reinforcing the value of retrieval/packing diagnostics.
The paper’s disciplined reporting of a negative result is valuable for the community and can reorient engineering choices in production agents. The limited scope and small operational N constrain claims but not the core cautionary lessons.

Strengths
Technical novelty and innovation
Clear, methodologically careful decomposition of operational effects (construction + presentation) vs. ranking quality; the paper isolates the selector as the only changing variable in the controlled study.
Negative-result contribution: a widely plausible hybrid scorer with time decay can systematically displace relevant content; the identified mechanism (query-independent recency outweighing lexical relevance) is insightful and actionable.
Transparent cost accounting that includes model-backed memory write costs, highlighting that query-only metering can misstate operational expense.
Experimental rigor and validation
Controlled selector study uses a frozen candidate bank, common packing policy, and stratified paired memory-cluster bootstrap with Holm correction; consistency across 512/1024/2048-token budgets strengthens conclusions.
Full-history retrieval sweep (no LLM in the loop) corroborates the selector ordering seen in QA accuracy, reducing concerns that results stem from reader/grade variance.
Paired operational design with matched character budgets and per-question audit linking evidence delivery to correctness.
Clarity of presentation
Very clear exposition of estimands, protocols, and limitations; diagrams help distinguish the two designs; equations and weights are specified; careful labeling of descriptive vs. inferential statistics.
Honest, prominent reporting of deviations from official evaluation protocols and limits of single-run Wilson intervals.
Significance of contributions
Highlights two important practitioner lessons: (1) do not conflate memory-query tokens with total system cost; (2) selector quality must be assessed independently from construction/representation choices.
The diagnosis of time-decay harm in hybrid memory selectors has immediate impact for system designers and could prevent widespread misconfiguration.