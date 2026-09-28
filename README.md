# Pipeline de Dados – Fintech

Pipeline em Python/Pandas que limpa, transforma e consolida logs de transações
financeiras, detecta anomalias via Z-Score e gera um relatório visual.

## Como executar

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python criar_dados.py   # gera transacoes.csv e cotacoes.csv
python main.py          # roda o pipeline; resultados em ./output
```

## O que o pipeline faz

| Etapa | Implementação |
|---|---|
| Ingestão | `pd.read_csv(..., encoding="latin1")` |
| Duplicatas | `drop_duplicates(keep="first")` (antes da imputação, para não distorcer a mediana) |
| Valores ausentes | `groupby("estado_cliente")["valor"].transform("median")` + `fillna` |
| Rastreabilidade | coluna `plataforma = "Mobile"` |
| Tempo | `datetime64[ns]` + `dt.tz_localize("America/Sao_Paulo")`; `dia_semana` e `mes` via `.dt` |
| Filtro | `(mes == 9) & ((estado == "SP") \| (estado == "RJ")) & (valor > 5000)` – bitwise, vetorizado |
| Risco | `id_cliente.map(risco_dict)` → `nivel_risco` |
| Pivot | `pivot_table(index="mes", columns="nivel_risco", aggfunc="sum", margins=True)` |
| Outliers | Z-Score por estado com `groupby().transform()` (sem `for`); anomalia se `Z > 2.5` |
| Gráfico | `fig, ax = plt.subplots()`; valor diário + `rolling(7).mean()`; `ax.set_ylim(bottom=0)` |

## Saídas (`output/`)

- `transacoes_limpas.csv` – base consolidada
- `filtro_setembro_sp_rj.csv` – filtro bitwise
- `pivot_mes_risco.csv` – tabela dinâmica com subtotais
- `anomalias_zscore.csv` – transações com Z > 2.5
- `grafico_transacoes_diarias.png` – valor diário e média móvel de 7 dias

## Premissas

- O dicionário `risco_dict` em `main.py` cobre C100–C104 (categorias fictícias; ajuste conforme a área de risco).
- A coluna `plataforma` é estática (`'Mobile'`), conforme o enunciado, mesmo existindo a coluna `origem`.
- Os dados gerados cobrem 1.000 horas (setembro e parte de outubro); a pivot considera todos os meses.
- Como a semente é fixa, os resultados são reproduzíveis.
