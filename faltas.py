import streamlit as st
import pandas as pd
from datetime import datetime
import psycopg2
import hashlib
import os

# Configuração da página
st.set_page_config(page_title="Sistema de Controle de Efetivo e Faltas", layout="wide", initial_sidebar_state="collapsed")

# --- CONEXÃO COM O SUPABASE (POSTGRESQL) ---
# Cole aqui embaixo o seu link completo do Supabase substituindo [YOUR-PASSWORD] pela sua senha real
SUPABASE_URL = "postgresql://postgres:1723Rsh32335770@db.jgzhlalaczpmecwqpofg.supabase.co:5432/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URL)

# --- FUNÇÃO DE CRIPTOGRAFIA DE SENHA ---
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# --- FUNÇÃO AUXILIAR DE MÁSCARA DE TELEFONE ---
def formatar_telefone(texto):
    digitos = "".join([c for c in str(texto) if c.isdigit()])
    if len(digitos) <= 10:
        if len(digitos) > 6:
            return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
        elif len(digitos) > 2:
            return f"({digitos[:2]}) {digitos[2:]}"
        elif len(digitos) > 0:
            return f"({digitos}"
        return ""
    else:
        if len(digitos) > 7:
            return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:11]}"
        elif len(digitos) > 2:
            return f"({digitos[:2]}) {digitos[2:]}"
        elif len(digitos) > 0:
            return f"({digitos}"
        return ""

# --- CONFIGURAÇÃO INICIAL DAS TABELAS NO SUPABASE ---
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS fracoes (
                        id SERIAL PRIMARY KEY,
                        nome_fracao TEXT UNIQUE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT UNIQUE,
                        identidade TEXT,
                        senha TEXT,
                        pg TEXT,
                        nome TEXT,
                        fracao TEXT,
                        perfil TEXT)''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS militares (
                        id SERIAL PRIMARY KEY,
                        identidade TEXT UNIQUE,
                        pg TEXT,
                        nome TEXT,
                        fracao TEXT,
                        celular TEXT DEFAULT '',
                        whatsapp TEXT DEFAULT '',
                        telefone TEXT DEFAULT '',
                        email TEXT DEFAULT '',
                        endereco TEXT DEFAULT '',
                        presenca INTEGER DEFAULT 0,
                        falta INTEGER DEFAULT 0,
                        justificativa TEXT DEFAULT '')''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS solicitacoes_mov (
                        id SERIAL PRIMARY KEY,
                        militar_id INTEGER,
                        tipo TEXT,
                        fracao_destino TEXT,
                        solicitante TEXT,
                        status TEXT DEFAULT 'PENDENTE')''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS solicitacoes_cadastro (
                        id SERIAL PRIMARY KEY,
                        identidade TEXT,
                        celular TEXT,
                        whatsapp TEXT,
                        telefone TEXT,
                        email TEXT,
                        endereco TEXT,
                        status TEXT DEFAULT 'PENDENTE')''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ausencias_futuras (
                        id SERIAL PRIMARY KEY,
                        nome_militar TEXT,
                        fracao TEXT,
                        data_prevista TEXT,
                        motivo TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS historico (
                        id SERIAL PRIMARY KEY,
                        data_hora TEXT,
                        pg TEXT,
                        nome TEXT,
                        fracao TEXT,
                        status TEXT,
                        justificativa TEXT,
                        gerente_responsavel TEXT)''')
                        
    conn.commit()
    
    # Dados padrões iniciais caso esteja vazio
    cursor.execute("SELECT COUNT(*) FROM fracoes")
    if cursor.fetchone()[0] == 0:
        fracoes_iniciais = [("1ª Seção",), ("2ª Seção",), ("3ª Seção",), ("S1",), ("S2",), ("COM/INFO",)]
        for f in fracoes_iniciais:
            cursor.execute("INSERT INTO fracoes (nome_fracao) VALUES (%s) ON CONFLICT DO NOTHING", f)
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        senha_padrao = hash_senha("1234")
        usuarios_iniciais = [
            ("admin", "000000", senha_padrao, "Cel", "Administrador Geral", "S1", "Administrador"),
            ("cmt", "111111", senha_padrao, "Ten Cel", "Comandante de Pelotão", "S1", "Comandante"),
            ("1sec", "222222", senha_padrao, "1º Sgt", "Sgt Chefe S1", "1ª Seção", "Gerente"),
            ("trindade", "333333", senha_padrao, "SD", "TRINDADE", "1ª Seção", "Convencional")
        ]
        for u in usuarios_iniciais:
            cursor.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, fracao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", u)
        
        militares_iniciais = [
            ("333333", "SD", "TRINDADE", "1ª Seção", "(51) 99999-1111", "(51) 99999-1111", "(51) 3333-1111", "trindade@exercito.mil.br", "Rua A, 100"),
            ("444444", "S Ten", "CEZARIO", "1ª Seção", "(51) 98888-2222", "(51) 98888-2222", "(51) 3333-2222", "cezario@exercito.mil.br", "Rua B, 200"),
            ("555555", "3º SGT", "CARLOS", "2ª Seção", "(51) 97777-3333", "(51) 97777-3333", "(51) 3333-3333", "carlos@exercito.mil.br", "Rua C, 300")
        ]
        for m in militares_iniciais:
            cursor.execute("INSERT INTO militares (identidade, pg, nome, fracao, celular, whatsapp, telefone, email, endereco) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", m)
        conn.commit()
        
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    st.error(f"Erro ao conectar ao Supabase. Verifique se o link e a senha estão corretos no código. Detalhes: {e}")
    st.stop()

# --- FUNÇÃO DE LOGIN ---
def login():
    if os.path.exists("brasao.png"):
        col_img, col_txt = st.columns([1, 8])
        with col_img:
            st.image("brasao.png", width=100)
        with col_txt:
            st.title("Sistema Integrado de Controle de Faltas")
            st.markdown("Identifique-se informando o seu **Usuário** ou **Identidade** e sua senha.")
    else:
        st.title("Sistema Integrado de Controle de Faltas")
        st.markdown("Identifique-se informando o seu **Usuário** ou **Identidade** e sua senha.")
    
    st.markdown("---")
    
    with st.form("login_form"):
        login_input = st.text_input("Usuário ou Nº de Identidade")
        senha = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar no Sistema")
        
        if submit:
            conn = get_connection()
            cursor = conn.cursor()
            senha_cript = hash_senha(senha)
            cursor.execute("SELECT usuario, identidade, pg, nome, fracao, perfil FROM usuarios WHERE (usuario = %s OR identidade = %s) AND senha = %s", (login_input, login_input, senha_cript))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                st.session_state.logado = True
                st.session_state.usuario_login = user[0]
                st.session_state.identidade_atual = user[1]
                st.session_state.nome_completo = f"{user[2]} {user[3]}"
                st.session_state.fracao = user[4]
                st.session_state.perfil = user[5]
                st.rerun()
            else:
                st.error("Usuário/Identidade ou senha incorretos!")

# --- PAINEL COMUM DE ATUALIZAÇÃO ---
def painel_convencional_comum():
    with st.expander("🔑 Alterar Minha Senha"):
        with st.form("form_senha"):
            nova_senha = st.text_input("Nova Senha", type="password")
            confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
            btn_trocar = st.form_submit_button("Salvar Nova Senha")
            if btn_trocar:
                if nova_senha == confirma_senha and len(nova_senha) > 0:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE usuarios SET senha = %s WHERE identidade = %s", (hash_senha(nova_senha), st.session_state.identidade_atual))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success("✅ Senha alterada com sucesso!")
                else:
                    st.error("As senhas não coincidem ou estão vazias.")

    with st.expander("📞 Atualizar Meus Dados para o Plano de Chamada"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT celular, whatsapp, telefone, email, endereco FROM militares WHERE identidade = %s", (st.session_state.identidade_atual,))
        dados_atuais = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if dados_atuais:
            with st.form("form_atualiza_dados"):
                st.caption("Ao clicar em 'Enviar', o sistema aplicará a máscara padrão nos telefones automaticamente.")
                c_cel = st.text_input("Celular (Apenas números)", value=dados_atuais[0])
                c_zap = st.text_input("WhatsApp (Apenas números)", value=dados_atuais[1])
                c_tel = st.text_input("Telefone Fixo (Apenas números)", value=dados_atuais[2])
                c_email = st.text_input("E-mail", value=dados_atuais[3])
                c_end = st.text_input("Endereço", value=dados_atuais[4])
                btn_env_dados = st.form_submit_button("Enviar para Aprovação do Administrador")
                
                if btn_env_dados:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO solicitacoes_cadastro (identidade, celular, whatsapp, telefone, email, endereco) VALUES (%s, %s, %s, %s, %s, %s)",
                                   (st.session_state.identidade_atual, formatar_telefone(c_cel), formatar_telefone(c_zap), formatar_telefone(c_tel), c_email, c_end))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success("📨 Dados formatados e enviados ao Administrador para aprovação!")

# --- 1. PERFIL: USUÁRIO CONVENCIONAL ---
def tela_convencional():
    st.title(f"👤 Painel do Militar - {st.session_state.nome_completo} ({st.session_state.fracao})")
    st.write("Consulte sua situação, registre avisos antecipados de ausência e atualize seus dados de contato.")
    
    painel_convencional_comum()
    
    st.markdown("---")
    st.subheader("🏥 Registrar Antecipadamente Ausência/Justificativa")
    with st.form("form_ausencia"):
        data_prevista = st.date_input("Data prevista da ausência")
        motivo = st.text_area("Justificativa / Motivo (Ex: Consulta médica, Dispensa, etc.)")
        enviar_aviso = st.form_submit_button("Enviar Aviso ao Gerente da Seção")
        
        if enviar_aviso:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ausencias_futuras (nome_militar, fracao, data_prevista, motivo) VALUES (%s, %s, %s, %s)",
                           (st.session_state.nome_completo, st.session_state.fracao, str(data_prevista), motivo))
            conn.commit()
            cursor.close()
            conn.close()
            st.success("✅ Aviso enviado com sucesso para o chefe da sua fração!")

    st.markdown("---")
    st.subheader("📋 Meu Histórico de Registros")
    conn = get_connection()
    df_hist = pd.read_sql_query("SELECT data_hora, status, justificativa, gerente_responsavel FROM historico WHERE nome = %s", conn, params=(st.session_state.nome_completo.split(' ', 1)[-1],))
    conn.close()
    if not df_hist.empty:
        st.dataframe(df_hist, hide_index=True, use_container_width=True)
    else:
        st.info("Nenhum registro de falta/presença encontrado no histórico.")

# --- 2. PERFIL: GERENTE DE FRAÇÃO ---
def tela_gerente():
    fracao = st.session_state.fracao
    st.title(f"📋 Chamada Diária - Fração: {fracao}")
    st.markdown(f"**Gerente Responsável:** {st.session_state.nome_completo}")
    
    painel_convencional_comum()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nome_militar, data_prevista, motivo FROM ausencias_futuras WHERE fracao = %s", (fracao,))
    avisos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if avisos:
        st.warning("⚠️ **Avisos Prévios de Ausência cadastrados por militares da sua fração:**")
        for av in avisos:
            st.markdown(f"- **{av[0]}** para o dia **{av[1]}**: *{av[2]}*")
            
    st.markdown("---")
    st.info("💡 Marque a presença ou falta. Se houver falta, preencha a justificativa.")
    
    conn = get_connection()
    df_militares = pd.read_sql_query("SELECT id, pg, nome, fracao, presenca, falta, justificativa FROM militares WHERE fracao = %s", conn, params=(fracao,))
    conn.close()
    
    editado = st.data_editor(
        df_militares,
        column_config={
            "id": None,
            "pg": st.column_config.TextColumn("P/G", disabled=True),
            "nome": st.column_config.TextColumn("NOME", disabled=True),
            "fracao": st.column_config.TextColumn("FRAÇÃO", disabled=True),
            "presenca": st.column_config.CheckboxColumn("PRESENÇA", default=False),
            "falta": st.column_config.CheckboxColumn("FALTA", default=False),
            "justificativa": st.column_config.TextColumn("JUSTIFICATIVA")
        },
        hide_index=True,
        use_container_width=True,
        key="editor_gerente"
    )
    
    if st.button("💾 Salvar Chamada da Seção", type="primary"):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        gerente_nome = st.session_state.nome_completo
        
        conn = get_connection()
        cursor = conn.cursor()
        for index, row in editado.iterrows():
            cursor.execute("UPDATE militares SET presenca = %s, falta = %s, justificativa = %s WHERE id = %s",
                           (int(row['presenca']), int(row['falta']), row['justificativa'], row['id']))
            
            if row['presenca'] or row['falta']:
                status = "PRESENTE" if row['presenca'] else "FALTOU"
                cursor.execute("INSERT INTO historico (data_hora, pg, nome, fracao, status, justificativa, gerente_responsavel) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                               (agora, row['pg'], row['nome'], row['fracao'], status, row['justificativa'], gerente_nome))
        conn.commit()
        cursor.close()
        conn.close()
        st.success("✅ Chamada registrada com sucesso!")

# --- 3. PERFIL: ADMINISTRADOR ---
def tela_administrador():
    st.title("🛡️ Painel do Administrador Geral")
    st.write("Gerenciamento de Frações, Efetivo, Plano de Chamada e Usuários.")
    
    painel_convencional_comum()
    
    conn = get_connection()
    fracoes_disponiveis = pd.read_sql_query("SELECT nome_fracao FROM fracoes", conn)['nome_fracao'].tolist()
    conn.close()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📌 Gerenciar Frações", "👥 Gestão de Efetivo", "📥 Movimentações", "📇 Contatos", "🔑 Usuários/Gerentes"])
    
    with tab1:
        st.subheader("Cadastro de Frações Oficiais do Sistema")
        st.write("Cadastre as frações aqui para que fiquem disponíveis em lista suspensa em todo o sistema.")
        
        with st.form("form_nova_fracao"):
            nova_fracao_input = st.text_input("Nome da Nova Fração (Ex: 3ª Seção)")
            btn_cad_fracao = st.form_submit_button("Adicionar Fração")
            if btn_cad_fracao and nova_fracao_input:
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO fracoes (nome_fracao) VALUES (%s)", (nova_fracao_input.strip(),))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f"Fração '{nova_fracao_input}' cadastrada com sucesso!")
                    st.rerun()
                except:
                    cursor.close()
                    conn.close()
                    st.error("Esta fração já está cadastrada.")
                
        st.markdown("---")
        st.subheader("Frações Atualmente Cadastradas")
        st.write(fracoes_disponiveis)
        
    with tab2:
        st.subheader("Adicionar Novo Militar ao Sistema")
        with st.form("novo_militar"):
            st.caption("Para telefones, você pode digitar apenas os números. O sistema formata automaticamente ao salvar.")
            c1, c2, c3, c4 = st.columns(4)
            with c1: nova_identidade = st.text_input("Nº Identidade (Login)")
            with c2: novo_pg = st.text_input("Posto/Graduação (Ex: 3º Sgt)")
            with c3: novo_nome = st.text_input("Nome de Guerra")
            with c4: 
                if fracoes_disponiveis:
                    nova_fracao = st.selectbox("Fração", fracoes_disponiveis)
                else:
                    nova_fracao = st.text_input("Fração (Cadastre na aba Frações)")
            
            c5, c6, c7, c8, c9 = st.columns(5)
            with c5: n_cel = st.text_input("Celular")
            with c6: n_zap = st.text_input("WhatsApp")
            with c7: n_tel = st.text_input("Telefone Fixo")
            with c8: n_email = st.text_input("E-mail")
            with c9: n_end = st.text_input("Endereço")
            
            cadastrar = st.form_submit_button("Cadastrar Militar Completo")
            if cadastrar:
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO militares (identidade, pg, nome, fracao, celular, whatsapp, telefone, email, endereco) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", 
                                   (nova_identidade, novo_pg, novo_nome, nova_fracao, formatar_telefone(n_cel), formatar_telefone(n_zap), formatar_telefone(n_tel), n_email, n_end))
                    cursor.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, fracao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                   (novo_nome.lower(), nova_identidade, hash_senha("1234"), novo_pg, novo_nome, nova_fracao, "Convencional"))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success("Militar cadastrado com sucesso (Senha padrão: 1234)!")
                except Exception as e:
                    cursor.close()
                    conn.close()
                    st.error(f"Erro: Identidade já cadastrada. ({e})")
                
        st.markdown("---")
        st.subheader("Efetivo Completo Cadastrado")
        conn = get_connection()
        df_all = pd.read_sql_query("SELECT * FROM militares", conn)
        conn.close()
        st.dataframe(df_all, hide_index=True, use_container_width=True)
        
    with tab3:
        st.subheader("Solicitações de Movimentação enviadas pelos Gerentes")
        conn = get_connection()
        df_sol = pd.read_sql_query("SELECT * FROM solicitacoes_mov WHERE status = 'PENDENTE'", conn)
        conn.close()
        
        if not df_sol.empty:
            for index, row in df_sol.iterrows():
                st.write(f"**Solicitante:** {row['solicitante']} | **Pedido:** {row['tipo']} | **Destino:** {row['fracao_destino']}")
                col_a, col_b = st.columns(2)
                if col_a.button(f"Aprovar Mov. #{row['id']}", key=f"aprov_{row['id']}"):
                    c = get_connection()
                    cur = c.cursor()
                    cur.execute("UPDATE solicitacoes_mov SET status = 'APROVADO' WHERE id = %s", (row['id'],))
                    c.commit()
                    cur.close()
                    c.close()
                    st.success("Aprovado!")
                    st.rerun()
                if col_b.button(f"Rejeitar Mov. #{row['id']}", key=f"rejei_{row['id']}"):
                    c = get_connection()
                    cur = c.cursor()
                    cur.execute("UPDATE solicitacoes_mov SET status = 'REJEITADO' WHERE id = %s", (row['id'],))
                    c.commit()
                    cur.close()
                    c.close()
                    st.warning("Rejeitado.")
                    st.rerun()
        else:
            st.info("Nenhuma solicitação de movimentação pendente.")

    with tab4:
        st.subheader("Solicitações de Atualização Cadastral (Plano de Chamada)")
        conn = get_connection()
        df_cad = pd.read_sql_query("SELECT * FROM solicitacoes_cadastro WHERE status = 'PENDENTE'", conn)
        conn.close()
        
        if not df_cad.empty:
            for index, row in df_cad.iterrows():
                st.write(f"**Identidade:** {row['identidade']} | **Novo Celular:** {row['celular']} | **Zap:** {row['whatsapp']} | **Endereço:** {row['endereco']}")
                col_c, col_d = st.columns(2)
                if col_c.button(f"Aprovar Cadastro #{row['id']}", key=f"cad_aprov_{row['id']}"):
                    c = get_connection()
                    cur = c.cursor()
                    cur.execute("UPDATE militares SET celular = %s, whatsapp = %s, telefone = %s, email = %s, endereco = %s WHERE identidade = %s",
                              (row['celular'], row['whatsapp'], row['telefone'], row['email'], row['endereco'], row['identidade']))
                    cur.execute("UPDATE solicitacoes_cadastro SET status = 'APROVADO' WHERE id = %s", (row['id'],))
                    c.commit()
                    cur.close()
                    c.close()
                    st.success("Dados cadastrais atualizados com sucesso!")
                    st.rerun()
                if col_d.button(f"Rejeitar Cadastro #{row['id']}", key=f"cad_rejei_{row['id']}"):
                    c = get_connection()
                    cur = c.cursor()
                    cur.execute("UPDATE solicitacoes_cadastro SET status = 'REJEITADO' WHERE id = %s", (row['id'],))
                    c.commit()
                    cur.close()
                    c.close()
                    st.warning("Rejeitado.")
                    st.rerun()
        else:
            st.info("Nenhuma solicitação de atualização cadastral pendente.")
            
    with tab5:
        st.subheader("Configurar / Atribuir Perfil de Usuário")
        with st.form("novo_user"):
            u_usuario = st.text_input('Nome de Usuário de Login (Ex: "3º Sgt Guerra")')
            u_identidade = st.text_input("Identidade do Militar")
            c_pg_u, c_nome_u = st.columns(2)
            with c_pg_u: u_pg = st.text_input("Posto/Graduação (Ex: 3º Sgt)")
            with c_nome_u: u_nome = st.text_input("Nome Completo")
            
            if fracoes_disponiveis:
                u_fracao = st.selectbox("Fração Atribuída", fracoes_disponiveis, key="select_fracao_user")
            else:
                u_fracao = st.text_input("Fração Atribuída")
                
            u_perfil = st.selectbox("Perfil de Acesso", ["Gerente", "Convencional", "Administrador", "Comandante"])
            criar_u = st.form_submit_button("Configurar Usuário")
            if criar_u:
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, fracao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (usuario) DO UPDATE SET identidade = EXCLUDED.identidade, senha = EXCLUDED.senha, pg = EXCLUDED.pg, nome = EXCLUDED.nome, fracao = EXCLUDED.fracao, perfil = EXCLUDED.perfil",
                                   (u_usuario.lower(), u_identidade, hash_senha("1234"), u_pg, u_nome, u_fracao, u_perfil))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success("Usuário configurado com sucesso! Senha padrão inicial: 1234")
                except Exception as e:
                    cursor.close()
                    conn.close()
                    st.error(f"Erro ao configurar: {e}")

# --- 4. PERFIL: COMANDANTE (4 ABAS) ---
def tela_comandante():
    if os.path.exists("brasao.png"):
        col_img, col_txt = st.columns([1, 8])
        with col_img:
            st.image("brasao.png", width=80)
        with col_txt:
            st.title("Painel do Comandante de Pelotão")
    else:
        st.title("Painel do Comandante de Pelotão")
        
    painel_convencional_comum()
    
    tab_mapa, tab_painel, tab_plano, tab_registros = st.tabs(["🗺️ MAPA (Ao Vivo)", "📊 Painel do Comandante", "📋 Plano de Chamada", "📑 Registros Diários"])
    
    conn = get_connection()
    df_militares = pd.read_sql_query("SELECT pg, nome, fracao, presenca, falta, justificativa FROM militares", conn)
    
    with tab_mapa:
        st.subheader("Mapa Geral do Efetivo em Tempo Real")
        df_mapa = df_militares.copy()
        df_mapa['STATUS'] = df_mapa.apply(lambda r: 'PRESENTE' if r['presenca']==1 else ('FALTOU' if r['falta']==1 else 'PENDENTE'), axis=1)
        st.dataframe(df_mapa[['pg', 'nome', 'fracao', 'STATUS', 'justificativa']], hide_index=True, use_container_width=True)
        
    with tab_painel:
        st.subheader("Métricas e Faltas ao Vivo")
        total = len(df_militares)
        presentes = len(df_militares[df_militares['presenca'] == 1])
        faltas = len(df_militares[df_militares['falta'] == 1])
        pendentes = total - presentes - faltas
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👥 Efetivo Total", total)
        c2.metric("✅ Presentes", presentes)
        c3.metric("❌ Faltas", faltas)
        c4.metric("⏳ Pendentes", pendentes)
        
        st.markdown("---")
        st.subheader("Relação de Faltas ao Vivo")
        df_faltas = df_militares[df_militares['falta'] == 1]
        if not df_faltas.empty:
            st.dataframe(df_faltas[['pg', 'nome', 'fracao', 'justificativa']], hide_index=True, use_container_width=True)
        else:
            st.success("Nenhuma falta registrada até o momento.")
            
        st.markdown("---")
        st.error("⚠️ **Área de Fechamento do Expediente**")
        if st.button("🧹 Registrar Fechamento e Limpar Chamada para o Próximo Dia", type="primary"):
            cursor = conn.cursor()
            cursor.execute("UPDATE militares SET presenca = 0, falta = 0, justificativa = ''")
            conn.commit()
            cursor.close()
            st.success("✅ Dados do dia arquivados no histórico e painel limpo com sucesso!")
            st.rerun()

    with tab_plano:
        st.subheader("Plano de Chamada (Dados de Contato e Endereço)")
        df_plano = pd.read_sql_query("SELECT pg, nome, fracao, celular, whatsapp, telefone, email, endereco FROM militares", conn)
        st.dataframe(df_plano, hide_index=True, use_container_width=True)

    with tab_registros:
        st.subheader("Registros Diários das Tiragens de Faltas")
        df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
        if not df_hist.empty:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_dia = st.text_input("Filtrar por Dia/Data (Ex: 24/07/2026)")
            with col_f2:
                filtro_gerente = st.text_input("Filtrar por Nome do Gerente")
                
            df_filtrado = df_hist.copy()
            if filtro_dia:
                df_filtrado = df_filtrado[df_filtrado['data_hora'].str.contains(filtro_dia, na=False)]
            if filtro_gerente:
                df_filtrado = df_filtrado[df_filtrado['gerente_responsavel'].str.contains(filtro_gerente, case=False, na=False)]
                
            st.dataframe(df_filtrado, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhum registro encontrado no histórico.")
            
    conn.close()

# --- FLUXO PRINCIPAL DA APLICAÇÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    login()
else:
    with st.sidebar:
        if os.path.exists("brasao.png"):
            st.image("brasao.png", width=80)
            
        st.markdown(f"👤 **{st.session_state.nome_completo}**")
        st.markdown(f"🆔 ID: **{st.session_state.identidade_atual}**")
        st.markdown(f"📍 Fração: **{st.session_state.fracao}**")
        st.markdown(f"🛡️ Perfil: **{st.session_state.perfil}**")
        st.markdown("---")
        if st.button("🚪 Sair do Sistema"):
            st.session_state.logado = False
            st.rerun()
            
    perfil = st.session_state.perfil
    if perfil == "Administrador":
        tela_administrador()
    elif perfil == "Comandante":
        tela_comandante()
    elif perfil == "Gerente":
        tela_gerente()
    elif perfil == "Convencional":
        tela_convencional()