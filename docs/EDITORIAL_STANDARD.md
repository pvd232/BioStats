# Editorial Standard for Technical White Papers

This standard applies to explanatory technical writing in any domain. A strong white paper should let its intended reader follow the system, mechanism, or argument without having to infer missing definitions, reconstruct hidden transitions, or sort essential concepts from incidental detail.

The governing aim is **selective completeness**, expressed through two linked obligations:

1. **Parsimony governs inclusion.** Omit a concept unless it materially advances the paper's central explanation.
2. **Explanatory completeness governs retained material.** Once a concept is included, explain it with enough depth, context, and precision for the intended reader to understand its role, using the canonical terminology and literature of the field.

Attention to detail is required at every scale. A technically correct sentence can still weaken the paper when its terminology is vague, its examples are poorly chosen, its relationship to the preceding paragraph is unclear, or its subject does not belong in the larger narrative.

## 1. Resolve ambiguity according to relevance

When a term or reference is ambiguous, first decide whether it belongs in the paper.

### Core ambiguity

A concept is core when later reasoning depends on it. Enrich the explanation until the reader can understand its concrete role. A useful explanation normally identifies:

1. what kind of thing the term names;
2. which component creates, owns, or performs it;
3. what information it receives;
4. what it does with that information;
5. what result or state change it produces; and
6. how that result enters the next stage of the narrative.

For example, “The launch groups those threads into thread blocks” makes *the launch* an unexplained actor. If launching is essential to the architecture, the paper must identify what performs the launch, what is submitted, how the grouping is specified, and what consumes that specification.

Likewise, saying that a scheduler “chooses work” is incomplete. A useful definition identifies the scheduler as a software or hardware mechanism, names the work it chooses among, identifies the available execution resources, and explains what the choice controls. The term becomes meaningful through its place in the mechanism.

### Superfluous ambiguity

A concept is superfluous when it introduces a side issue that the paper never uses. Remove the sentence or reference instead of expanding it into a new tangent. Explanation is warranted by relevance, not merely by the presence of unfamiliar terminology.

This distinction prevents two opposite failures: leaving a necessary concept undefined and overloading the paper by explaining an unnecessary one.

## 2. Explain mechanisms rather than renaming them

Replacing one unfamiliar phrase with another does not create understanding. A definition should expose concrete behavior.

The description “an independently schedulable path of instruction execution” followed by “an operating-system record” moves between two abstractions without explaining either. It leaves unanswered what is executing, what state must be saved, what the scheduler operates on, and how execution resumes. This is a general **noun-substitution anti-pattern**: the prose supplies increasingly technical labels while withholding the mechanism.

Definitions should answer the reader's immediate follow-up questions. If a component “dispatches,” “resolves,” “binds,” “materializes,” “orchestrates,” or “manages” something, state what concrete input it examines, what decision or transformation occurs, and what receives the result.

Avoid definitions that rely on vague category words such as *record*, *request*, *boundary*, *context*, *state*, *path*, or *layer* unless the relevant fields, owner, lifetime, and operational role are explained. These words can be precise after their referents have been established; by themselves, they conceal missing information.

## 3. Use established terminology and define it at first use

Prefer terminology documented in the relevant technical standards, primary documentation, or established literature. Avoid invented, ornamental, or nondescriptive jargon.

A specialized term belongs when it names a real distinction needed by the paper. At first use, explain the term in ordinary language and connect it to the surrounding mechanism. Later sections may then use the term without repetition.

Do not introduce a local taxonomy, ontology, formula, abbreviation, or named state merely to make the paper appear formal. A genuinely necessary local convention must be identified as such, defined completely, and used consistently. Otherwise, use the established nomenclature of the field.

Watch especially for terms that sound precise while saying little: *control plane*, *execution boundary*, *realization policy*, *artifact layer*, *stateful pathway*, and similar constructions. Their technical tone is not evidence of explanatory value.

## 4. Preserve causal and logical continuity

Present mechanisms in the order that control, data, or evidence actually moves:

**producer → input or representation → operation → result → consumer**

Each paragraph should be a smooth logical continuation of the preceding discussion. The transition should usually be implicit in the subject matter; mechanical signposting such as “this follows because” is unnecessary.

“The training code obtains the next batch and calls PyTorch” is awkward when the preceding text has not established that a batch now exists, which component produced it, or why control has moved to the training code. The general problem is a **missing causal bridge**. Restore the missing action or revise the preceding paragraph so that it ends where the next one begins.

“Host memory is not a lower level of this on-device cache hierarchy” is an **orphaned corrective claim** when no preceding passage creates that misconception. If the relationship matters, explain the relevant memory path and hardware boundary in positive terms where the distinction becomes necessary. If it does not matter, remove the sentence.

Avoid abrupt changes in abstraction level. A paragraph should not move from high-level program behavior to low-level fields, hardware details, or provenance requirements without establishing why the reader now needs that level of detail.

## 5. Eliminate vague referents and empty transitions

Review every occurrence of words such as *this*, *that*, *these*, *those*, *it*, *the process*, *the transition*, *the boundary*, *the implementation*, and *the operation*. Preserve them when one antecedent is unmistakable. Replace them with the exact noun when several interpretations are possible.

The passage “The transition begins before the batch exists. At that boundary, the persistent training state includes...” fails because neither *transition* nor *boundary* identifies a concrete event. The paragraph then compounds the ambiguity with an inventory of state, control variables, input-pipeline behavior, and random generators. The general infraction combines an undefined reference, an abrupt shift of subject, excessive abstraction, and an unmotivated list.

A transition sentence must carry technical content. Remove prose that merely announces a topic, comments on presentation strategy, or claims that a classification is useful without teaching the classification itself.

## 6. Control lists, tables, and option inventories

A list is useful when its entries form a defined set for the stated scope, represent ordered stages, or answer the same explicit question. A table is useful when the same meaningful attributes are compared across every row.

Introduce the organizing principle before presenting the entries. Explain each entry's role in the mechanism. The reader should know whether the list is exhaustive, representative, conditional, or ordered.

Avoid **grab-bag lists** assembled from related terms that belong to different dimensions or stages. Such lists increase apparent coverage while weakening understanding. If only two entries matter to the argument, explain those two and omit the rest.

For example:

> An artifact is a stored representation produced or consumed by the toolchain: a source file, object file, library, bytecode module, executable, debugging-symbol file, or deployment package.

The examples occupy different stages, serve different consumers, and describe different kinds of grouping. The list does not establish which property makes them relevant to the current argument. This is a general **enumeration-as-definition anti-pattern**: examples are substituted for a coherent definition. Define the property the paper actually needs, then introduce only the representations required to follow the mechanism.

The sentence “Artifacts are best classified along independent axes rather than placed in one flat list” does not repair the problem. It comments on the writer's classification strategy without stating the classifications or showing how they clarify the system. This is **metadiscourse without technical content**.

A passage can also be locally precise and globally unnecessary. A detailed distinction between a library and a deployment package may be accurate, yet still appear from nowhere and lead nowhere. Technical correctness does not satisfy the inclusion threshold by itself. The passage must resolve a question created by the narrative or support a later claim.

For example:

> Tensor device, dtype, shape, layout, and autograd state determine eligible execution paths. PyTorch selects native code, an external library routine, or generated code.

This passage presents two dense option inventories without explaining which property affects which decision, who performs the selection, or what the selected categories mean. The broader failure is **unresolved combinatorial prose**: many possible inputs are paired with many possible outcomes while the causal mapping remains hidden. Repair it by following one representative decision end to end, then add another dimension only if the central argument needs it.

## 7. Keep the paper lean without making it incomplete

Parsimony is the default. The burden is on each sentence, example, and subsection to justify its presence by advancing the central explanation. Retain a detail when a later core claim depends on it, when it resolves a likely ambiguity in a core mechanism, or when evidence is needed to support the argument. Remove:

- unrelated technical facts;
- implementation trivia that does not change the explanation;
- speculative possibilities not tied to the described system;
- redundant caveats;
- decorative analogies;
- invented examples that introduce additional concepts; and
- commentary about how the writer chose to organize the material.

Every retained mechanism must then be explained far enough to be understood. Inclusion creates an explanatory obligation; a passing reference to a complicated concept is not a substitute for teaching it. Brevity achieved by deleting necessary definitions produces a glossary of jargon. Comprehensiveness achieved by inventorying every adjacent concept produces an unreadable survey. Selective completeness avoids both failures.

Conditional components should be presented conditionally. Do not imply that every implementation contains a component or source of state merely because some implementations do.

## 8. Use examples and equations only when they perform explanatory work

An example should instantiate the mechanism just explained and should be small enough that every part can be connected to the prose. Prefer a single concrete path over a catalogue of hypothetical variants.

An analogy should clarify a structural relationship without introducing misleading behavior. Remove it when the literal mechanism can be explained just as clearly.

An equation should express a real dependency used by the argument. Define every symbol and explain why the relationship appears at that point. Avoid invented formulas, state tuples, or transformations whose main purpose is to give ordinary prose a formal appearance.

## 9. Use contrast and caveats deliberately

State the positive mechanism directly when it is sufficient. Repeated constructions such as “it is not X; it is Y” make the paper sound like a correction to an unseen draft and often introduce misconceptions the reader did not have.

Contrast is appropriate when two plausible concepts are easily confused and the distinction materially affects the argument. In that case, explain both concepts and the consequence of confusing them.

Do not include revision history, apologies, references to earlier wording, or commentary about removed approaches in the finished paper. The document should read as a clean, self-contained account.

## 10. Ground claims in verified sources

Use primary documentation for implementation behavior and established standards or peer-reviewed literature for conceptual, mathematical, and scientific claims. A citation must support the specific sentence or paragraph to which it is attached.

Distinguish documented behavior from inference, recommendation, and proposed convention. Label a local design as a proposal instead of presenting it as a standard. Qualify implementation-dependent claims by version, platform, or configuration when those conditions matter.

Verified sourcing also disciplines terminology. If a term cannot be located in authoritative literature, determine whether the paper truly needs a new term or whether established language already expresses the idea more clearly.

## 11. Maintain consistency at every scale

Sentence-level clarity, paragraph-level continuity, section-level relevance, and document-level coherence are separate requirements. A sentence may be grammatical and technically accurate while remaining irrelevant to its paragraph. A paragraph may be informative while interrupting the section's causal sequence. A section may be rigorous while exceeding the paper's intended scope.

The introduction should establish the question and scope. Each section should advance that question at a deliberate level of abstraction. The conclusion should synthesize the argument actually developed in the body. Terminology, assumptions, examples, diagrams, and claims should remain consistent across all three.

Local improvement must preserve global consistency. A new explanation should not create duplication, contradiction, a premature term, an obsolete summary, or an isolated detour elsewhere. Once the paper is coherent, accurate, appropriately scoped, and well sourced, further editing should require a specific identified deficiency.

## 12. Final review checklist

For each technical term:

- Is it standard, necessary, and defined at first use?
- Is its explanation consistent with the field's canonical literature?
- Does the definition explain concrete behavior rather than substitute another noun?
- If it remains ambiguous, should it be enriched or removed?

For each paragraph:

- Does it continue naturally from the preceding mechanism or argument?
- Are the actor, action, input, and result identifiable?
- Are pronouns and compressed references unambiguous?
- Does every detail advance the central explanation?
- Could the paragraph be removed without weakening that explanation? If so, remove it.

For each list, table, example, and equation:

- What explicit question does it answer?
- Are its entries comparable and properly scoped?
- Is every item explained and subsequently useful?
- Would a direct paragraph or one concrete example teach the idea more clearly?

For the complete document:

- Is the narrative coherent, consistent, and simple without omitting core mechanisms?
- Is the paper informative without being overloaded?
- Are claims grounded in verified sources and established terminology?
- Have revisionist language, speculative commentary, irrelevant detail, and invented formalism been removed?
- Do the introduction, body, diagrams, and conclusion describe the same architecture or argument?
- Does the rendered document preserve headings, links, equations, code, figures, and readable transitions?
