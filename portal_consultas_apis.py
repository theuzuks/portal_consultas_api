import json
import threading
import urllib.parse
import urllib.request
import webbrowser

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# Função reutilizável para consultar APIs externas com tratamento simples de erro.
def buscar_json(url, timeout=15):
    requisicao = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        conteudo = resposta.read().decode("utf-8")
        return json.loads(conteudo)


# --- APIs do Pokémon ---
def buscar_pokemon(identificador):
    termo = urllib.parse.quote(str(identificador).strip().lower())
    dados = buscar_json(f"https://pokeapi.co/api/v2/pokemon/{termo}")
    stats = {}
    for item in dados.get("stats", []):
        nome_stat = item["stat"]["name"]
        stats[nome_stat] = item["base_stat"]

    tipos = [tipo["type"]["name"] for tipo in dados.get("types", [])]
    sprite = (
        dados.get("sprites", {})
        .get("other", {})
        .get("official-artwork", {})
        .get("front_default")
        or dados.get("sprites", {}).get("front_default")
    )

    return {
        "id": dados.get("id"),
        "name": dados.get("name").title(),
        "sprite": sprite,
        "types": tipos,
        "height": dados.get("height") / 10,
        "weight": dados.get("weight") / 10,
        "stats": {
            "hp": stats.get("hp", 0),
            "attack": stats.get("attack", 0),
            "defense": stats.get("defense", 0),
            "speed": stats.get("speed", 0),
        },
    }


@app.route("/api/pokemon/info", methods=["POST"])
def api_pokemon_info():
    dados = request.get_json(silent=True) or {}
    identificador = (dados.get("pokedex") or "").strip()

    if not identificador:
        return jsonify({"error": "Informe um nome ou número para buscar o Pokémon."}), 400

    try:
        pokemon = buscar_pokemon(identificador)
        return jsonify({"success": True, "pokemon": pokemon})
    except Exception:
        return jsonify({
            "error": "Não foi possível encontrar esse Pokémon. Verifique o nome ou o número digitado."
        }), 404


@app.route("/api/pokemon/battle", methods=["POST"])
def api_pokemon_battle():
    dados = request.get_json(silent=True) or {}
    primeiro = (dados.get("primeiro") or "").strip()
    segundo = (dados.get("segundo") or "").strip()

    if not primeiro or not segundo:
        return jsonify({"error": "Informe os dois Pokémon para a batalha."}), 400

    try:
        pokemon_a = buscar_pokemon(primeiro)
        pokemon_b = buscar_pokemon(segundo)
        total_a = sum(pokemon_a["stats"].values())
        total_b = sum(pokemon_b["stats"].values())

        if total_a > total_b:
            vencedor = "primeiro"
        elif total_b > total_a:
            vencedor = "segundo"
        else:
            vencedor = "empate"

        return jsonify({
            "success": True,
            "primeiro": pokemon_a,
            "segundo": pokemon_b,
            "vencedor": vencedor,
            "totais": {"primeiro": total_a, "segundo": total_b},
        })
    except Exception:
        return jsonify({
            "error": "Não foi possível completar a batalha. Verifique os nomes ou números informados."
        }), 404


# --- API do CEP ---
def formatar_cep(cep):
    return f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep


@app.route("/api/cep", methods=["POST"])
def api_cep():
    dados = request.get_json(silent=True) or {}
    cep = (dados.get("cep") or "").strip()
    cep_limpo = cep.replace("-", "").replace(".", "").replace(" ", "")

    if not cep_limpo.isdigit() or len(cep_limpo) != 8:
        return jsonify({"error": "Informe um CEP válido no formato 00000-000."}), 400

    try:
        resposta = buscar_json(f"https://viacep.com.br/ws/{cep_limpo}/json/")
    except Exception:
        return jsonify({"error": "Não foi possível consultar o CEP neste momento."}), 503

    if resposta.get("erro"):
        return jsonify({"error": "CEP não encontrado. Verifique o número informado."}), 404

    return jsonify({
        "success": True,
        "logradouro": resposta.get("logradouro") or "Não informado",
        "bairro": resposta.get("bairro") or "Não informado",
        "cidade": resposta.get("localidade") or "Não informado",
        "estado": resposta.get("uf") or "Não informado",
        "ddd": resposta.get("ddd") or "Não informado",
        "cep_formatado": formatar_cep(cep_limpo),
    })


# --- API da cotação do dólar ---
@app.route("/api/dolar")
def api_dolar():
    try:
        dados = buscar_json("https://economia.awesomeapi.com.br/json/last/USD-BRL")
    except Exception:
        return jsonify({"error": "Não foi possível carregar a cotação do dólar agora."}), 503

    cotacao = dados.get("USDBRL")
    if not cotacao:
        return jsonify({"error": "Dados da cotação indisponíveis no momento."}), 404

    try:
        valor_compra = float(cotacao.get("bid", 0))
        valor_venda = float(cotacao.get("ask", 0))
        variacao = float(cotacao.get("pctChange", 0))
        horario = cotacao.get("create_date", "Não disponível")
    except (TypeError, ValueError):
        return jsonify({"error": "A resposta da cotação está em formato inválido."}), 500

    return jsonify({
        "success": True,
        "compra": valor_compra,
        "venda": valor_venda,
        "variacao": variacao,
        "horario": horario,
    })


# Página principal com a interface em HTML + CSS + JavaScript.
@app.route("/")
def index():
    return render_template_string(r"""
    <!DOCTYPE html>
    <html lang="pt-BR" data-theme="light">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Portal de Consultas</title>
        <style>
            :root {
                --bg: #edf3ff;
                --bg-secondary: #dfe9ff;
                --panel: rgba(255, 255, 255, 0.84);
                --panel-strong: #ffffff;
                --panel-alt: #f4f7ff;
                --text: #1f2a37;
                --muted: #65758b;
                --border: rgba(148, 163, 184, 0.28);
                --primary: #3b82f6;
                --primary-strong: #1d4ed8;
                --primary-soft: rgba(59, 130, 246, 0.12);
                --success: #16a34a;
                --success-soft: rgba(34, 197, 94, 0.12);
                --danger: #dc2626;
                --danger-soft: rgba(220, 38, 38, 0.12);
                --warning: #f59e0b;
                --shadow: 0 16px 32px rgba(30, 41, 59, 0.12);
                --input: #f8fafc;
            }

            html[data-theme="dark"] {
                --bg: #0f172a;
                --bg-secondary: #111827;
                --panel: rgba(15, 23, 42, 0.88);
                --panel-strong: #111827;
                --panel-alt: #172033;
                --text: #e5eefc;
                --muted: #9aa9be;
                --border: rgba(148, 163, 184, 0.18);
                --primary: #60a5fa;
                --primary-strong: #93c5fd;
                --primary-soft: rgba(96, 165, 250, 0.12);
                --success: #4ade80;
                --success-soft: rgba(74, 222, 128, 0.12);
                --danger: #f87171;
                --danger-soft: rgba(248, 113, 113, 0.12);
                --warning: #fbbf24;
                --shadow: 0 18px 36px rgba(2, 6, 23, 0.38);
                --input: #0b1220;
            }

            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                min-height: 100vh;
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, var(--bg) 0%, var(--bg-secondary) 100%);
                color: var(--text);
                transition: background 0.3s ease, color 0.3s ease;
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 32px 20px 48px;
            }

            .topbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 16px;
                margin-bottom: 24px;
            }

            .brand {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .brand h1 {
                margin: 0;
                font-size: clamp(1.7rem, 2vw, 2.3rem);
                letter-spacing: -0.04em;
            }

            .brand span {
                color: var(--muted);
                font-size: 0.96rem;
            }

            .theme-toggle {
                border: 1px solid var(--border);
                background: var(--panel);
                color: var(--text);
                padding: 11px 16px;
                border-radius: 999px;
                font-size: 0.95rem;
                font-weight: 700;
                cursor: pointer;
                transition: transform 0.25s ease, box-shadow 0.25s ease;
                box-shadow: var(--shadow);
            }

            .theme-toggle:hover {
                transform: translateY(-1px);
            }

            .cards-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 22px;
            }

            .card {
                position: relative;
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 24px;
                box-shadow: var(--shadow);
                padding: 22px 20px 18px;
                overflow: hidden;
                backdrop-filter: blur(10px);
                transition: transform 0.25s ease, border-color 0.25s ease;
            }

            .card:hover {
                transform: translateY(-2px);
                border-color: rgba(59, 130, 246, 0.35);
            }

            .card-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 14px;
            }

            .card-header h2 {
                margin: 0;
                font-size: 1.3rem;
            }

            .badge {
                background: var(--primary-soft);
                color: var(--primary-strong);
                padding: 7px 10px;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.02em;
            }

            .card form {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .input-group {
                display: flex;
                align-items: center;
                gap: 10px;
                background: var(--input);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 0 12px;
                transition: border-color 0.2s ease, box-shadow 0.2s ease;
            }

            .input-group:focus-within {
                border-color: var(--primary);
                box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
            }

            input {
                width: 100%;
                border: none;
                outline: none;
                background: transparent;
                color: var(--text);
                font-size: 1rem;
                padding: 13px 0;
            }

            button {
                border: none;
                border-radius: 12px;
                background: linear-gradient(135deg, var(--primary) 0%, var(--primary-strong) 100%);
                color: white;
                padding: 12px 16px;
                font-size: 0.95rem;
                font-weight: 700;
                cursor: pointer;
                transition: filter 0.2s ease, transform 0.2s ease;
            }

            button:hover {
                filter: brightness(1.04);
                transform: translateY(-1px);
            }

            .button-row {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
            }

            .secondary {
                background: var(--panel-alt);
                color: var(--text);
                border: 1px solid var(--border);
            }

            .loading {
                display: none;
                align-items: center;
                justify-content: center;
                gap: 10px;
                padding: 14px 10px;
                color: var(--muted);
                font-weight: 600;
            }

            .loading.visible {
                display: flex;
            }

            .spinner {
                width: 18px;
                height: 18px;
                border: 3px solid rgba(148, 163, 184, 0.3);
                border-top-color: var(--primary);
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }

            @keyframes spin {
                to { transform: rotate(360deg); }
            }

            .result {
                display: none;
                margin-top: 16px;
                padding-top: 14px;
                border-top: 1px solid var(--border);
            }

            .result.visible {
                display: block;
            }

            .status-message {
                padding: 12px 14px;
                border-radius: 12px;
                font-weight: 600;
                background: var(--panel-alt);
                color: var(--text);
                border: 1px solid var(--border);
            }

            .status-message.error {
                background: var(--danger-soft);
                color: var(--danger);
                border-color: rgba(220, 38, 38, 0.2);
            }

            .status-message.success {
                background: var(--success-soft);
                color: var(--success);
                border-color: rgba(34, 197, 94, 0.2);
            }

            .poke-card {
                display: grid;
                grid-template-columns: 110px 1fr;
                gap: 14px;
                align-items: center;
                background: var(--panel-alt);
                border: 1px solid var(--border);
                border-radius: 18px;
                padding: 14px;
                margin-top: 12px;
            }

            .poke-card img {
                width: 100%;
                max-width: 100px;
                aspect-ratio: 1;
                object-fit: contain;
                display: block;
            }

            .poke-card h3 {
                margin: 0 0 4px;
                font-size: 1.2rem;
            }

            .meta {
                color: var(--muted);
                font-size: 0.85rem;
            }

            .pill-list {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 8px;
            }

            .pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 6px 10px;
                border-radius: 999px;
                background: rgba(59, 130, 246, 0.1);
                color: var(--primary-strong);
                font-size: 0.8rem;
                font-weight: 700;
            }

            .stat-list {
                display: grid;
                gap: 10px;
                margin-top: 14px;
            }

            .stat-row {
                display: grid;
                grid-template-columns: 80px 1fr 48px;
                gap: 10px;
                align-items: center;
            }

            .stat-row span {
                font-size: 0.8rem;
                font-weight: 700;
                color: var(--muted);
                text-transform: uppercase;
            }

            .bar {
                position: relative;
                width: 100%;
                height: 10px;
                border-radius: 999px;
                background: rgba(148, 163, 184, 0.24);
                overflow: hidden;
            }

            .bar-fill {
                position: absolute;
                inset: 0 auto 0 0;
                border-radius: inherit;
                background: linear-gradient(90deg, #3b82f6, #10b981);
            }

            .valor {
                text-align: right;
                font-weight: 700;
                color: var(--text);
                font-size: 0.8rem;
            }

            .battle-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                margin-top: 12px;
            }

            .battle-card {
                background: var(--panel-alt);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 12px;
            }

            .winner-box {
                margin-top: 12px;
                border-radius: 14px;
                padding: 12px 14px;
                background: var(--success-soft);
                border: 1px solid rgba(34, 197, 94, 0.12);
                color: var(--success);
                font-weight: 700;
            }

            .cep-block,
            .dolar-block {
                display: grid;
                gap: 10px;
                margin-top: 10px;
            }

            .info-line {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 10px;
                padding: 8px 10px;
                background: var(--panel-alt);
                border: 1px solid var(--border);
                border-radius: 10px;
            }

            .info-line strong {
                color: var(--muted);
                font-weight: 700;
            }

            .dolar-price {
                display: flex;
                flex-direction: column;
                gap: 4px;
                padding: 14px;
                border-radius: 16px;
                background: var(--panel-alt);
                border: 1px solid var(--border);
            }

            .dolar-price .valor-principal {
                font-size: clamp(1.4rem, 2vw, 2rem);
                font-weight: 800;
                letter-spacing: -0.04em;
            }

            .always-visible {
                display: block;
            }

            .up {
                color: var(--success);
            }

            .down {
                color: var(--danger);
            }

            @media (max-width: 980px) {
                .cards-grid {
                    grid-template-columns: 1fr;
                }
            }

            @media (max-width: 560px) {
                .container {
                    padding: 20px 14px 30px;
                }

                .topbar {
                    flex-direction: column;
                    align-items: flex-start;
                }

                .button-row {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header class="topbar">
                <div class="brand">
                    <h1>Portal de Consultas</h1>
                    <span>Informações rápidas e úteis em um só lugar</span>
                </div>
                <button id="themeToggle" class="theme-toggle" type="button" aria-label="Alternar tema">
                    🌙 Tema escuro
                </button>
            </header>

            <main class="cards-grid">
                <section class="card" id="pokemonInfoCard">
                    <div class="card-header">
                        <h2>Pokédex</h2>
                        <span class="badge">Informações</span>
                    </div>
                    <form id="pokemonInfoForm">
                        <div class="input-group">
                            <input id="pokemonInfoInput" type="text" placeholder="Digite nome ou número" maxlength="50" />
                        </div>
                        <button type="submit">Consultar Pokémon</button>
                    </form>
                    <div class="loading" id="pokemonInfoLoading">
                        <div class="spinner"></div>
                        <span>Buscando Pokémon...</span>
                    </div>
                    <div class="result" id="pokemonInfoResult"></div>
                </section>

                <section class="card" id="pokemonBattleCard">
                    <div class="card-header">
                        <h2>Pokédex</h2>
                        <span class="badge">Batalha</span>
                    </div>
                    <form id="pokemonBattleForm">
                        <div class="input-group">
                            <input id="pokemonBattleInputA" type="text" placeholder="Primeiro Pokémon" maxlength="50" />
                        </div>
                        <div class="input-group">
                            <input id="pokemonBattleInputB" type="text" placeholder="Segundo Pokémon" maxlength="50" />
                        </div>
                        <button type="submit">Comparar</button>
                    </form>
                    <div class="loading" id="pokemonBattleLoading">
                        <div class="spinner"></div>
                        <span>Simulando batalha...</span>
                    </div>
                    <div class="result" id="pokemonBattleResult"></div>
                </section>

                <section class="card" id="cepCard">
                    <div class="card-header">
                        <h2>Consulta de CEP</h2>
                        <span class="badge">Endereço</span>
                    </div>
                    <form id="cepForm">
                        <div class="input-group">
                            <input id="cepInput" type="text" inputmode="numeric" maxlength="9" placeholder="00000-000" />
                        </div>
                        <button type="submit">Buscar CEP</button>
                    </form>
                    <div class="loading" id="cepLoading">
                        <div class="spinner"></div>
                        <span>Consultando endereço...</span>
                    </div>
                    <div class="result" id="cepResult"></div>
                </section>

                <section class="card" id="dolarCard">
                    <div class="card-header">
                        <h2>Cotação do dólar</h2>
                        <span class="badge">Moeda</span>
                    </div>
                    <div class="dolar-block" id="dolarBlock">
                        <div class="dolar-price">
                            <div class="meta">Última atualização</div>
                            <div id="dolarHorario" class="meta">--</div>
                            <div class="valor-principal" id="dolarValor">R$ 0,00</div>
                            <div id="dolarVariacao" class="meta">--</div>
                        </div>
                        <div class="input-group">
                            <input id="dolarInput" type="number" min="0" step="0.01" placeholder="Valor em dólares" />
                        </div>
                        <div class="button-row">
                            <button id="dolarConverterBtn" type="button">Converter</button>
                            <button id="dolarAtualizarBtn" class="secondary" type="button">Atualizar</button>
                        </div>
                        <div id="dolarResultado" class="status-message">Valor em reais aparecerá aqui.</div>
                    </div>
                    <div class="loading" id="dolarLoading">
                        <div class="spinner"></div>
                        <span>Atualizando cotação...</span>
                    </div>
                </section>
            </main>
        </div>

        <script>
            const THEME_KEY = 'portal-theme';

            function escapeHtml(value) {
                return String(value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#039;');
            }

            function applyTheme(theme) {
                document.documentElement.setAttribute('data-theme', theme);
                const btn = document.getElementById('themeToggle');
                btn.textContent = theme === 'dark' ? '☀️ Tema claro' : '🌙 Tema escuro';
                localStorage.setItem(THEME_KEY, theme);
            }

            function formatCurrency(value) {
                return new Intl.NumberFormat('pt-BR', {
                    style: 'currency',
                    currency: 'BRL',
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                }).format(value);
            }

            function formatNumber(value) {
                return Number(value).toLocaleString('pt-BR', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                });
            }

            function setLoading(cardId, isLoading) {
                const card = document.getElementById(cardId);
                const loader = card.querySelector('.loading');
                const result = card.querySelector('.result');

                if (loader) loader.classList.toggle('visible', isLoading);
                if (result) result.classList.toggle('visible', !isLoading);
            }

            function showCardMessage(cardId, message, tipo = 'error') {
                const container = document.getElementById(cardId);
                const result = container ? (container.querySelector('.result') || container) : null;
                if (!result) return;
                result.innerHTML = `<div class="status-message ${tipo}">${escapeHtml(message)}</div>`;
                if (result.classList) result.classList.add('visible');
            }

            function renderPokemonInfo(data) {
                const result = document.getElementById('pokemonInfoResult');
                const pokemon = data.pokemon;
                const statEntries = Object.entries(pokemon.stats);
                const statsHtml = statEntries.map(([key, value]) => {
                    const labels = { hp: 'HP', attack: 'Ataque', defense: 'Defesa', speed: 'Velocidade' };
                    const percent = Math.min((value / 255) * 100, 100);
                    return `
                        <div class="stat-row">
                            <span>${labels[key] || key}</span>
                            <div class="bar"><div class="bar-fill" style="width:${percent}%"></div></div>
                            <div class="valor">${value}</div>
                        </div>
                    `;
                }).join('');

                result.innerHTML = `
                    <div class="poke-card">
                        <img src="${escapeHtml(pokemon.sprite || 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/0.png')}" alt="${escapeHtml(pokemon.name)}" />
                        <div>
                            <h3>${escapeHtml(pokemon.name)}</h3>
                            <div class="meta">#${pokemon.id}</div>
                            <div class="pill-list">
                                ${(pokemon.types || []).map(tipo => `<span class="pill">${escapeHtml(tipo)}</span>`).join('')}
                            </div>
                            <div class="meta" style="margin-top: 10px;">Altura: ${pokemon.height.toFixed(1)} m · Peso: ${pokemon.weight.toFixed(1)} kg</div>
                        </div>
                    </div>
                    <div class="stat-list">${statsHtml}</div>
                `;
                result.classList.add('visible');
            }

            function renderPokemonBattle(data) {
                const result = document.getElementById('pokemonBattleResult');
                const primeiro = data.primeiro;
                const segundo = data.segundo;
                const vencedorMap = {
                    primeiro: `${primeiro.name} venceu!`,
                    segundo: `${segundo.name} venceu!`,
                    empate: 'A batalha terminou em empate!'
                };
                const vencedor = vencedorMap[data.vencedor] || 'Resultado indefinido';

                result.innerHTML = `
                    <div class="battle-grid">
                        <div class="battle-card">
                            <div class="poke-card" style="grid-template-columns: 1fr; margin-top: 0;">
                                <img src="${escapeHtml(primeiro.sprite || 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/0.png')}" alt="${escapeHtml(primeiro.name)}" />
                                <div>
                                    <h3>${escapeHtml(primeiro.name)}</h3>
                                    <div class="meta">#${primeiro.id}</div>
                                    <div class="pill-list">
                                        ${(primeiro.types || []).map(tipo => `<span class="pill">${escapeHtml(tipo)}</span>`).join('')}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="battle-card">
                            <div class="poke-card" style="grid-template-columns: 1fr; margin-top: 0;">
                                <img src="${escapeHtml(segundo.sprite || 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/0.png')}" alt="${escapeHtml(segundo.name)}" />
                                <div>
                                    <h3>${escapeHtml(segundo.name)}</h3>
                                    <div class="meta">#${segundo.id}</div>
                                    <div class="pill-list">
                                        ${(segundo.types || []).map(tipo => `<span class="pill">${escapeHtml(tipo)}</span>`).join('')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="winner-box">${escapeHtml(vencedor)} · Total: ${data.totais.primeiro} x ${data.totais.segundo}</div>
                `;
                result.classList.add('visible');
            }

            function renderCep(data) {
                const result = document.getElementById('cepResult');
                result.innerHTML = `
                    <div class="cep-block">
                        <div class="info-line"><strong>CEP</strong><span>${escapeHtml(data.cep_formatado)}</span></div>
                        <div class="info-line"><strong>Logradouro</strong><span>${escapeHtml(data.logradouro)}</span></div>
                        <div class="info-line"><strong>Bairro</strong><span>${escapeHtml(data.bairro)}</span></div>
                        <div class="info-line"><strong>Cidade</strong><span>${escapeHtml(data.cidade)}</span></div>
                        <div class="info-line"><strong>Estado</strong><span>${escapeHtml(data.estado)}</span></div>
                        <div class="info-line"><strong>DDD</strong><span>${escapeHtml(data.ddd)}</span></div>
                    </div>
                `;
                result.classList.add('visible');
            }

            async function buscarPokemonInfo() {
                const input = document.getElementById('pokemonInfoInput');
                const valor = input.value.trim();
                if (!valor) {
                    showCardMessage('pokemonInfoResult', 'Digite um nome ou número para consultar o Pokémon.', 'error');
                    return;
                }

                const cardId = 'pokemonInfoCard';
                const loader = document.getElementById('pokemonInfoLoading');
                loader.classList.add('visible');
                const result = document.getElementById('pokemonInfoResult');
                result.classList.remove('visible');

                try {
                    const response = await fetch('/api/pokemon/info', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ pokedex: valor }),
                    });
                    const data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(data.error || 'Não foi possível buscar o Pokémon.');
                    }

                    renderPokemonInfo(data);
                } catch (error) {
                    showCardMessage(cardId, error.message || 'Erro ao consultar o Pokémon.', 'error');
                } finally {
                    loader.classList.remove('visible');
                }
            }

            async function buscarPokemonBattle() {
                const inputA = document.getElementById('pokemonBattleInputA');
                const inputB = document.getElementById('pokemonBattleInputB');
                const valorA = inputA.value.trim();
                const valorB = inputB.value.trim();

                if (!valorA || !valorB) {
                    showCardMessage('pokemonBattleResult', 'Informe os dois Pokémon para a batalha.', 'error');
                    return;
                }

                const loader = document.getElementById('pokemonBattleLoading');
                loader.classList.add('visible');
                const result = document.getElementById('pokemonBattleResult');
                result.classList.remove('visible');

                try {
                    const response = await fetch('/api/pokemon/battle', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ primeiro: valorA, segundo: valorB }),
                    });
                    const data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(data.error || 'Não foi possível fazer a comparação.');
                    }

                    renderPokemonBattle(data);
                } catch (error) {
                    showCardMessage('pokemonBattleResult', error.message || 'Erro ao comparar os Pokémon.', 'error');
                } finally {
                    loader.classList.remove('visible');
                }
            }

            async function buscarCep() {
                const input = document.getElementById('cepInput');
                const valor = input.value.trim();
                const cepValido = /^\d{5}-\d{3}$/.test(valor) || /^\d{8}$/.test(valor);

                if (!cepValido) {
                    showCardMessage('cepResult', 'Informe um CEP válido no formato 00000-000.', 'error');
                    return;
                }

                const loader = document.getElementById('cepLoading');
                loader.classList.add('visible');
                const result = document.getElementById('cepResult');
                result.classList.remove('visible');

                try {
                    const response = await fetch('/api/cep', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ cep: valor }),
                    });
                    const data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(data.error || 'Não foi possível consultar o CEP.');
                    }

                    renderCep(data);
                } catch (error) {
                    showCardMessage('cepResult', error.message || 'Erro ao consultar o CEP.', 'error');
                } finally {
                    loader.classList.remove('visible');
                }
            }

            async function buscarDolar() {
                const loader = document.getElementById('dolarLoading');
                loader.classList.add('visible');

                try {
                    const response = await fetch('/api/dolar');
                    const data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(data.error || 'Não foi possível carregar a cotação.');
                    }

                    const value = Number(data.compra || 0);
                    const horario = data.horario || 'Não informado';
                    const variacao = Number(data.variacao || 0);
                    const valorTexto = formatCurrency(value);
                    const variacaoTexto = `${variacao >= 0 ? '▲' : '▼'} ${formatNumber(Math.abs(variacao))}%`;

                    document.getElementById('dolarHorario').textContent = horario;
                    document.getElementById('dolarValor').textContent = valorTexto;
                    const variacaoEl = document.getElementById('dolarVariacao');
                    variacaoEl.textContent = variacaoTexto;
                    variacaoEl.className = `meta ${variacao >= 0 ? 'up' : 'down'}`;
                } catch (error) {
                    const resultado = document.getElementById('dolarResultado');
                    resultado.className = 'status-message error';
                    resultado.textContent = error.message || 'Erro ao buscar cotação.';
                } finally {
                    loader.classList.remove('visible');
                }
            }

            function converterDolar() {
                const valor = Number(document.getElementById('dolarInput').value || 0);
                const cotacao = Number(document.getElementById('dolarValor').textContent.replace(/[^\d,.-]/g, '').replace('.', '').replace(',', '.')) || 0;
                const total = valor * cotacao;
                const output = document.getElementById('dolarResultado');
                output.className = 'status-message success';
                output.textContent = `${formatNumber(valor)} USD = ${formatCurrency(total)}`;
            }

            function formatarCepInput(event) {
                let value = event.target.value.replace(/\D/g, '');
                if (value.length > 5) {
                    value = value.slice(0, 5) + '-' + value.slice(5, 8);
                }
                event.target.value = value.slice(0, 9);
            }

            document.getElementById('pokemonInfoForm').addEventListener('submit', function (event) {
                event.preventDefault();
                buscarPokemonInfo();
            });

            document.getElementById('pokemonBattleForm').addEventListener('submit', function (event) {
                event.preventDefault();
                buscarPokemonBattle();
            });

            document.getElementById('cepForm').addEventListener('submit', function (event) {
                event.preventDefault();
                buscarCep();
            });

            document.getElementById('dolarConverterBtn').addEventListener('click', converterDolar);
            document.getElementById('dolarAtualizarBtn').addEventListener('click', buscarDolar);
            document.getElementById('cepInput').addEventListener('input', formatarCepInput);
            document.getElementById('pokemonInfoInput').addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    buscarPokemonInfo();
                }
            });
            document.getElementById('pokemonBattleInputA').addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    buscarPokemonBattle();
                }
            });
            document.getElementById('pokemonBattleInputB').addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    buscarPokemonBattle();
                }
            });
            document.getElementById('cepInput').addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    buscarCep();
                }
            });
            document.getElementById('dolarInput').addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    converterDolar();
                }
            });

            document.getElementById('themeToggle').addEventListener('click', function () {
                const current = document.documentElement.getAttribute('data-theme');
                applyTheme(current === 'dark' ? 'light' : 'dark');
            });

            const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
            applyTheme(savedTheme);
            buscarDolar();
        </script>
    </body>
    </html>
    """)


# Abre o navegador automaticamente quando o programa é executado.
def abrir_navegador():
    webbrowser.open('http://127.0.0.1:5000/', new=2)


if __name__ == "__main__":
    threading.Timer(1.2, abrir_navegador).start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
