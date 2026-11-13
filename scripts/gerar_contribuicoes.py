"""Gera o calendário de contribuições do perfil em português, inglês e alemão.

Saída: assets/contribuicoes.svg (pt), assets/contribuicoes.en.svg e assets/contribuicoes.de.svg.
Usa só a biblioteca padrão. Lê o token de GITHUB_TOKEN (no GitHub Actions), GH_TOKEN ou
GITHUB_PAT. Em caso de erro, sai com código 1 e não toca nos SVGs existentes, para o README
continuar mostrando a última versão boa.

Uso local:  GITHUB_PAT=... python scripts/gerar_contribuicoes.py
Sem acesso direto à API: python scripts/gerar_contribuicoes.py --json resposta.json
(resposta.json = saída da mesma consulta GraphQL, obtida com curl ou gh api)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

USUARIO = os.environ.get("PERFIL_USUARIO", "CodeByMarlon")
ASSETS = Path(__file__).resolve().parent.parent / "assets"

CONSULTA = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
  }
}
"""

CORES = {
    "NONE": "#162036",
    "FIRST_QUARTILE": "#0B4F5E",
    "SECOND_QUARTILE": "#0E7490",
    "THIRD_QUARTILE": "#06B6D4",
    "FOURTH_QUARTILE": "#67E8F9",
}
CELULA, PASSO = 17, 21
MESES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

TEXTOS = {
    "pt": dict(arquivo="contribuicoes.svg", milhar=".",
               titulo="{total} contribuições no último ano",
               sub="inclui contribuições em repositórios privados · dados até {data}",
               desc="Calendário de contribuições de {usuario}: {total} no último ano, {ativos} dias ativos, {atual} semanas "
                    "seguidas com contribuição (recorde de {recorde_sem}) e recorde de {recorde_dia} em um dia. Inclui "
                    "repositórios privados. Dados até {data}.",
               recorde="recorde em um dia", ativos="dias ativos", semanas="semanas seguidas",
               rodape="gerado todo dia pelo GitHub Actions com a API GraphQL", menos="menos", mais="mais",
               meses=["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
               dias=("seg", "qua", "sex"), data=lambda d: f"{d:%d/%m/%Y}"),
    "en": dict(arquivo="contribuicoes.en.svg", milhar=",",
               titulo="{total} contributions in the last year",
               sub="includes contributions to private repositories · data through {data}",
               desc="Contribution calendar for {usuario}: {total} in the last year, {ativos} active days, {atual} weeks "
                    "in a row with contributions (record: {recorde_sem}) and a best day of {recorde_dia}. Includes "
                    "private repositories. Data through {data}.",
               recorde="best single day", ativos="active days", semanas="weeks in a row",
               rodape="generated daily by GitHub Actions with the GraphQL API", menos="less", mais="more",
               meses=MESES_EN, dias=("Mon", "Wed", "Fri"),
               data=lambda d: f"{MESES_EN[d.month - 1]} {d.day}, {d.year}"),
    "de": dict(arquivo="contribuicoes.de.svg", milhar=".",
               titulo="{total} Beiträge im letzten Jahr",
               sub="inklusive Beiträge in privaten Repositories · Stand: {data}",
               desc="Beitragskalender von {usuario}: {total} im letzten Jahr, {ativos} aktive Tage, {atual} Wochen in "
                    "Folge mit Beiträgen (Rekord: {recorde_sem}) und bis zu {recorde_dia} an einem Tag. Inklusive "
                    "privater Repositories. Stand: {data}.",
               recorde="Rekord an einem Tag", ativos="aktive Tage", semanas="Wochen in Folge",
               rodape="täglich per GitHub Actions über die GraphQL-API erstellt", menos="weniger", mais="mehr",
               meses=["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
               dias=("Mo", "Mi", "Fr"), data=lambda d: f"{d:%d.%m.%Y}"),
}


def buscar_calendario(token: str) -> dict:
    corpo = json.dumps({"query": CONSULTA, "variables": {"login": USUARIO}}).encode()
    pedido = urllib.request.Request(
        "https://api.github.com/graphql",
        data=corpo,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "perfil-readme-contribuicoes"},
    )
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        dados = json.load(resposta)
    if dados.get("errors"):
        raise RuntimeError(dados["errors"])
    return dados["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def milhar(n: int, separador: str) -> str:
    return f"{n:,}".replace(",", separador)


def sequencia_semanal(semanas: list[list[dict]]) -> tuple[int, int]:
    """Semanas seguidas com contribuição: (atual, recorde). A semana em curso sem nada não quebra a atual."""
    somas = [sum(d["contributionCount"] for d in s) for s in semanas]
    recorde = corrida = 0
    for soma in somas:
        corrida = corrida + 1 if soma else 0
        recorde = max(recorde, corrida)
    atual = 0
    for i, soma in enumerate(reversed(somas)):
        if soma:
            atual += 1
        elif i > 0:
            break
    return atual, recorde


def montar_svg(cal: dict, t: dict) -> str:
    semanas = [s["contributionDays"] for s in cal["weeks"]]
    dias = [d for s in semanas for d in s]
    total = milhar(cal["totalContributions"], t["milhar"])
    ativos = sum(1 for d in dias if d["contributionCount"])
    recorde_dia = max(d["contributionCount"] for d in dias)
    atual, recorde_sem = sequencia_semanal(semanas)
    data = t["data"](date.fromisoformat(dias[-1]["date"]))

    n = len(semanas)
    largura_grade = n * PASSO - 4
    x0 = round((1280 - (largura_grade + 44)) / 2 + 44)
    y0 = 128
    altura = 326

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="{altura}" viewBox="0 0 1280 {altura}" '
         'role="img" aria-labelledby="titulo desc">',
         f'  <title id="titulo">{t["titulo"].format(total=total)}</title>',
         '  <desc id="desc">' + t["desc"].format(usuario=USUARIO, total=total, ativos=ativos, atual=atual,
                                                recorde_sem=recorde_sem, recorde_dia=recorde_dia, data=data) + '</desc>',
         '  <style>',
         "    .sans{font-family:'Segoe UI',Inter,'Helvetica Neue',Arial,sans-serif}",
         '    .sem{animation:ent .6s ease-out both}',
         '    @keyframes ent{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}',
         '    @media (prefers-reduced-motion:reduce){.sem{animation:none}.mov{display:none}}',
         '  </style>',
         f'  <rect x="1" y="1" width="1278" height="{altura - 2}" rx="20" fill="#0B1222" stroke="#1E293B" stroke-width="2"/>',
         '  <g class="sans">',
         f'    <text x="40" y="54" font-size="26" font-weight="700" fill="#F1F5F9">{t["titulo"].format(total=total)}</text>',
         f'    <text x="40" y="84" font-size="16" fill="#64748B">{t["sub"].format(data=data)}</text>']

    destaques = [(905, recorde_dia, t["recorde"], "#A78BFA"), (1075, ativos, t["ativos"], "#34D399"),
                 (1240, atual, t["semanas"], "#22D3EE")]
    for x, valor, rotulo, cor in destaques:
        s += [f'    <text x="{x}" y="52" font-size="30" font-weight="800" fill="{cor}" text-anchor="end">{valor}</text>',
              f'    <text x="{x}" y="76" font-size="15" fill="#94A3B8" text-anchor="end">{rotulo}</text>']

    ultimo_rotulo = -10
    for i, semana in enumerate(semanas):
        primeiro = date.fromisoformat(semana[0]["date"])
        anterior = date.fromisoformat(semanas[i - 1][0]["date"]) if i else None
        if (anterior is None or primeiro.month != anterior.month) and i - ultimo_rotulo >= 3:
            if i == 0 and primeiro.day > 7:
                continue
            s.append(f'    <text x="{x0 + i * PASSO}" y="{y0 - 10}" font-size="15" fill="#64748B">{t["meses"][primeiro.month - 1]}</text>')
            ultimo_rotulo = i
    for dia_semana, nome in zip((1, 3, 5), t["dias"]):
        s.append(f'    <text x="{x0 - 10}" y="{y0 + dia_semana * PASSO + 13}" font-size="14" fill="#64748B" '
                 f'text-anchor="end">{nome}</text>')
    s.append('  </g>')

    for i, semana in enumerate(semanas):
        x = x0 + i * PASSO
        s.append(f'  <g class="sem" style="animation-delay:{i * 0.014:.3f}s">')
        for d in semana:
            y = y0 + d["weekday"] * PASSO
            s.append(f'    <rect x="{x}" y="{y}" width="{CELULA}" height="{CELULA}" rx="4" fill="{CORES[d["contributionLevel"]]}"/>')
        s.append('  </g>')

    ux = x0 + (n - 1) * PASSO
    uy = y0 + dias[-1]["weekday"] * PASSO
    s += [f'  <rect class="mov" x="{ux - 2}" y="{uy - 2}" width="{CELULA + 4}" height="{CELULA + 4}" rx="5" '
          'fill="none" stroke="#F8FAFC" stroke-width="1.5">',
          '    <animate attributeName="stroke-opacity" values=".9;.1;.9" dur="2s" repeatCount="indefinite"/>',
          '  </rect>']

    fim = x0 + largura_grade
    base = y0 + 7 * PASSO + 26
    s += ['  <g class="sans" font-size="14" fill="#64748B">',
          f'    <text x="{x0}" y="{base}">{t["rodape"]}</text>',
          f'    <text x="{fim - 5 * 19 - 46}" y="{base}" text-anchor="end">{t["menos"]}</text>']
    for j, cor in enumerate(CORES.values()):
        s.append(f'    <rect x="{fim - 40 - (5 - j) * 19}" y="{base - 12}" width="14" height="14" rx="3" fill="{cor}"/>')
    s += [f'    <text x="{fim - 34}" y="{base}">{t["mais"]}</text>', '  </g>', '</svg>', '']
    return "\n".join(s)


def main() -> int:
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--json":
            dados = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
            calendario = dados["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        else:
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_PAT")
            if not token:
                print("Defina GITHUB_TOKEN (ou GH_TOKEN/GITHUB_PAT).", file=sys.stderr)
                return 1
            calendario = buscar_calendario(token)
    except (urllib.error.URLError, RuntimeError, KeyError, TypeError, OSError, ValueError) as erro:
        print(f"Falha ao ler as contribuições: {erro}", file=sys.stderr)
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    for t in TEXTOS.values():
        (ASSETS / t["arquivo"]).write_text(montar_svg(calendario, t), encoding="utf-8", newline="\n")
    print(f"{calendario['totalContributions']} contribuições -> {', '.join(t['arquivo'] for t in TEXTOS.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
