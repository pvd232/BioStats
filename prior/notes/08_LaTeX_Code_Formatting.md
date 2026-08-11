# LaTeX Code Formatting

- Original conversation: [LaTeX Code Formatting](chatgpt-conversation://67f31fd6-e9a0-800c-b86a-9a2d74cb89e9)
- Archive type: substantive reconstruction; not a verbatim transcript.

## Request

The user wanted the LaTeX equivalent of Markdown's inline backtick formatting for code, filenames, paths, and identifiers.

## Inline code

The basic command is

```latex
\texttt{experiments/hw1/hw1.py}
```

It renders its argument in a monospaced/typewriter font. Special LaTeX characters still need escaping inside `\texttt{}`:

```latex
\texttt{learning\_rate=10\^\{-3\}}
```

For literal paths or code containing many special characters, `\verb` is more convenient:

```latex
\verb|experiments/hw1/hw1.py|
```

The delimiter can be any character not present in the content, for example `\verb!...!`. `\verb` cannot be used normally inside command arguments, captions, or section headings.

## Longer code blocks

For simple preformatted text:

```latex
\begin{verbatim}
python experiments/hw1/hw1.py
\end{verbatim}
```

For formatted source code, common packages are `listings` and `minted`:

```latex
\usepackage{listings}

\begin{lstlisting}[language=Python]
optimizer = Adam(model.parameters(), lr=1e-3)
\end{lstlisting}
```

`minted` provides strong syntax highlighting through Pygments but usually requires compilation with `-shell-escape`.

## Recommended rule

- Use `\texttt{}` for short identifiers when normal LaTeX escaping is manageable.
- Use `\verb` for literal inline code or paths.
- Use `lstlisting` or `minted` for multiline code.

