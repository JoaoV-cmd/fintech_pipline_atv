"""
Pipeline de dados - Fintech
---------------------------
Limpa, transforma e consolida transações financeiras, detecta anomalias
(Z-Score por estado) e gera um relatório visual.

Uso:
    python criar_dados.py   # gera transacoes.csv e cotacoes.csv
    python main.py          # executa o pipeline e grava os resultados em ./output
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend não interativo: funciona em servidores/CI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ARQUIVO_TRANSACOES = Path("transacoes.csv")
PASTA_SAIDA = Path("output")
FUSO = "America/Sao_Paulo"
LIMITE_Z = 2.5

# Categoria de risco por cliente (usada com .map())
RISCO_DICT = {
    "C100": "Baixo",
    "C101": "Alto",
    "C102": "Médio",
    "C103": "Baixo",
    "C104": "Alto",
}


# ---------------------------------------------------------------------------
# 1. Ingestão e limpeza
# ---------------------------------------------------------------------------
def carregar_transacoes(caminho: Path) -> pd.DataFrame:
    """Lê o CSV legado (latin1) e converte a data para datetime64[ns]."""
    df = pd.read_csv(caminho, encoding="latin1")
    df["data_transacao"] = pd.to_datetime(df["data_transacao"]).astype("datetime64[ns]")
    return df


def imputar_valor_por_estado(df: pd.DataFrame) -> pd.DataFrame:
    """Substitui NaN em 'valor' pela mediana do respectivo estado (vetorizado)."""
    mediana_estado = df.groupby("estado_cliente")["valor"].transform("median")
    df["valor"] = df["valor"].fillna(mediana_estado)
    return df


# ---------------------------------------------------------------------------
# 2. Engenharia de dados e alinhamento temporal
# ---------------------------------------------------------------------------
def enriquecer_tempo(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica fuso horário e cria colunas de dia da semana e mês via .dt."""
    df["data_transacao"] = df["data_transacao"].dt.tz_localize(FUSO)
    df["dia_semana"] = df["data_transacao"].dt.day_name()
    df["mes"] = df["data_transacao"].dt.month
    return df


# ---------------------------------------------------------------------------
# 3. Filtro bitwise
# ---------------------------------------------------------------------------
def filtrar_setembro_alto_valor(df: pd.DataFrame) -> pd.DataFrame:
    """Setembro & (SP | RJ) & valor > 5000, usando somente operadores bitwise."""
    mascara = (
        (df["mes"] == 9)
        & ((df["estado_cliente"] == "SP") | (df["estado_cliente"] == "RJ"))
        & (df["valor"] > 5000)
    )
    return df[mascara]


# ---------------------------------------------------------------------------
# 4. Cruzamento e agregação
# ---------------------------------------------------------------------------
def adicionar_risco(df: pd.DataFrame, risco_dict: dict) -> pd.DataFrame:
    df["nivel_risco"] = df["id_cliente"].map(risco_dict)
    return df


def tabela_dinamica(df: pd.DataFrame) -> pd.DataFrame:
    """Soma do valor por mês (linhas) x nível de risco (colunas) com subtotais."""
    return pd.pivot_table(
        df,
        values="valor",
        index="mes",
        columns="nivel_risco",
        aggfunc="sum",
        margins=True,
        margins_name="Total",
    )


# ---------------------------------------------------------------------------
# 5. Outliers (Z-Score vetorizado)
# ---------------------------------------------------------------------------
def calcular_zscore(df: pd.DataFrame, coluna: str = "valor", grupo: str = "estado_cliente") -> pd.Series:
    """Z = (x - mu) / sigma, calculado por grupo, sem laços for."""
    g = df.groupby(grupo)[coluna]
    mu = g.transform("mean")
    sigma = g.transform("std")
    # sigma == 0 (grupo sem variação) -> Z = 0, evitando divisão por zero
    return ((df[coluna] - mu) / sigma.replace(0, np.nan)).fillna(0.0)


def detectar_anomalias(df: pd.DataFrame, limite: float = LIMITE_Z) -> pd.DataFrame:
    df = df.assign(z_score=calcular_zscore(df))
    return df[df["z_score"] > limite]


# ---------------------------------------------------------------------------
# 6. Visualização (API orientada a objetos)
# ---------------------------------------------------------------------------
def gerar_grafico(df: pd.DataFrame, destino: Path) -> None:
    diario = df.set_index("data_transacao")["valor"].resample("D").sum()
    media_movel = diario.rolling(7).mean()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(diario.index, diario.values, color="tab:blue", alpha=0.6,
            label="Valor total diário")
    ax.plot(media_movel.index, media_movel.values, color="tab:red", linewidth=2.5,
            label="Média móvel de 7 dias")

    ax.set_ylim(bottom=0)
    ax.set_title("Valor total de transações por dia e média móvel de 7 dias")
    ax.set_xlabel("Data")
    ax.set_ylabel("Valor total (R$)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="upper right")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def main() -> None:
    PASTA_SAIDA.mkdir(exist_ok=True)

    df = carregar_transacoes(ARQUIVO_TRANSACOES)
    print(f"Linhas carregadas: {len(df)}")

    # Duplicatas removidas ANTES da imputação, para que linhas repetidas
    # não distorçam a mediana por estado.
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    print(f"Linhas após remover duplicatas: {len(df)}")

    df = imputar_valor_por_estado(df)
    df["plataforma"] = "Mobile"
    df = enriquecer_tempo(df)
    df = adicionar_risco(df, RISCO_DICT)

    filtradas = filtrar_setembro_alto_valor(df)
    print(f"Transações de setembro (SP/RJ, > R$ 5.000): {len(filtradas)}")

    pivot = tabela_dinamica(df)
    print("\nTabela dinâmica (soma do valor por mês x risco):")
    print(pivot.round(2))

    anomalias = detectar_anomalias(df)
    print(f"\nAnomalias (Z > {LIMITE_Z}): {len(anomalias)}")

    gerar_grafico(df, PASTA_SAIDA / "grafico_transacoes_diarias.png")

    df.to_csv(PASTA_SAIDA / "transacoes_limpas.csv", index=False, encoding="utf-8")
    filtradas.to_csv(PASTA_SAIDA / "filtro_setembro_sp_rj.csv", index=False, encoding="utf-8")
    pivot.to_csv(PASTA_SAIDA / "pivot_mes_risco.csv", encoding="utf-8")
    anomalias.to_csv(PASTA_SAIDA / "anomalias_zscore.csv", index=False, encoding="utf-8")
    print(f"\nResultados gravados em '{PASTA_SAIDA}/'")


if __name__ == "__main__":
    main()
