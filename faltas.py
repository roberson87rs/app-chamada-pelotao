import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Controle de Faltas", layout="wide", initial_sidebar_state="collapsed")

# --- DADOS FALSOS PARA TESTE (SIMULANDO SUA PLANILHA) ---
if 'db_militares' not in st.session_state:
    st.session_state.db_militares = pd.DataFrame({
        'P/G': ['S Ten', '1º SGT', '2º SGT', '3º SGT', 'CB', 'SD EP', '2º SGT', '3º SGT', '2º SGT', '3º SGT', '1º SGT', '3º SGT'],
        'NOME': ['CEZARIO', 'RAMOS', 'HERNANDEZ', 'JAQUELINE', 'GOMES', 'TRINDADE', 'MAX COSTA', 'YAMANAKA', 'KELVIN', 'CARLOS ARIEL', 'LEANDRO BRITO', 'MARIA EDILENE'],
        'FRAÇÃO': ['1ª SEÇ', '1ª SEÇ', '1ª SEÇ', '1ª SEÇ', '1ª SEÇ', '1ª SEÇ', '2ª SEÇ', '2ª SEÇ', '3ª SEÇ', '3ª SEÇ', 'SAÚDE', 'SAÚDE'],
        'PRESENÇA': [False]*12,
        'FALTA': [False]*12,
        'JUSTIFICATIVA': ['']*12
    })

if 'historico' not in st.session_state:
    st.session_state.historico = pd.DataFrame(columns=['DATA_HORA', 'P/G', 'NOME', 'FRAÇÃO', 'STATUS', 'JUSTIFICATIVA', 'QUEM_PREENCHEU'])

# --- CONTROLE DE ACESSO (USUÁRIOS) ---
# Na versão final, isso virá do Google Sheets
USUARIOS = {
    "1sec": {"senha": "123", "fracao": "1ª SEÇ", "perfil": "SGT"},
    "2sec": {"senha": "123", "fracao": "2ª SEÇ", "perfil": "SGT"},
    "3sec": {"senha": "123", "fracao": "3ª SEÇ", "perfil": "SGT"},
    "saude": {"senha": "123", "fracao": "SAÚDE", "perfil": "SGT"},
    "cmt": {"senha": "cmt", "fracao": "TODAS", "perfil": "CMT"}
}

# --- FUNÇÃO DE LOGIN ---
def login():
    st.title("🔒 Acesso - Controle de Faltas")
    st.write("Digite o usuário e senha para acessar sua fração.")
    with st.form("login_form"):
        usuario = st.text_input("Usuário (Ex: 1sec, saude, cmt)")
        senha = st.text_input("Senha (Ex: 123, cmt)", type="password")
        submit = st.form_submit_button("Entrar")
        
        if submit:
            if usuario in USUARIOS and USUARIOS[usuario]['senha'] == senha:
                st.session_state.logado = True
                st.session_state.usuario_atual = usuario
                st.session_state.perfil = USUARIOS[usuario]['perfil']
                st.session_state.fracao = USUARIOS[usuario]['fracao']
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos!")

# --- TELA DO SARGENTO (CHAMADA) ---
def tela_sargento():
    fracao = st.session_state.fracao
    st.title(f"📋 Tiragem de Faltas - {fracao}")
    st.markdown(f"**Preenchedor:** {st.session_state.usuario_atual.upper()}")
    
    # Filtra a base para a fração do sargento
    df_fracao = st.session_state.db_militares[st.session_state.db_militares['FRAÇÃO'] == fracao].copy()
    
    st.info("💡 Marque a caixa correspondente e adicione a justificativa se houver falta.")
    
    # O Editor de Dados (A "Planilha Viva")
    editado = st.data_editor(
        df_fracao,
        column_config={
            "P/G": st.column_config.TextColumn(disabled=True),
            "NOME": st.column_config.TextColumn(disabled=True),
            "FRAÇÃO": st.column_config.TextColumn(disabled=True),
            "PRESENÇA": st.column_config.CheckboxColumn("PRESENÇA", default=False),
            "FALTA": st.column_config.CheckboxColumn("FALTA", default=False),
            "JUSTIFICATIVA": st.column_config.TextColumn("JUSTIFICATIVA")
        },
        hide_index=True,
        use_container_width=True,
        key="editor_chamada"
    )
    
    if st.button("💾 Salvar Chamada do Dia", type="primary"):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        novos_registros = []
        
        for index, row in editado.iterrows():
            # Atualiza a base principal (foto do dia)
            st.session_state.db_militares.loc[st.session_state.db_militares['NOME'] == row['NOME'], ['PRESENÇA', 'FALTA', 'JUSTIFICATIVA']] = [row['PRESENÇA'], row['FALTA'], row['JUSTIFICATIVA']]
            
            # Prepara o histórico se alguma caixa foi marcada
            if row['PRESENÇA'] or row['FALTA']:
                status = "PRESENTE" if row['PRESENÇA'] else "FALTOU"
                novos_registros.append({
                    'DATA_HORA': agora,
                    'P/G': row['P/G'],
                    'NOME': row['NOME'],
                    'FRAÇÃO': row['FRAÇÃO'],
                    'STATUS': status,
                    'JUSTIFICATIVA': row['JUSTIFICATIVA'],
                    'QUEM_PREENCHEU': st.session_state.usuario_atual
                })
            
        # Salva no histórico
        if novos_registros:
            df_novos = pd.DataFrame(novos_registros)
            st.session_state.historico = pd.concat([st.session_state.historico, df_novos], ignore_index=True)
            st.success("✅ Chamada salva e enviada com sucesso!")
        else:
            st.warning("⚠️ Nenhuma presença ou falta foi marcada.")

# --- TELA DO COMANDANTE (PAINEL GERAL) ---
def tela_cmt():
    st.title("⭐ Painel do Comandante de Pelotão")
    st.write("Visão geral em tempo real de todas as frações.")
    
    df = st.session_state.db_militares
    
    # Métricas
    total = len(df)
    presentes = len(df[df['PRESENÇA'] == True])
    faltas = len(df[df['FALTA'] == True])
    pendentes = total - presentes - faltas
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Efetivo Total", total)
    col2.metric("✅ Presentes", presentes)
    col3.metric("❌ Faltas", faltas)
    col4.metric("⏳ Pendentes", pendentes)
    
    st.markdown("---")
    st.subheader("🔴 Resumo de Faltas do Dia")
    df_faltas = df[df['FALTA'] == True]
    if not df_faltas.empty:
        st.dataframe(df_faltas[['P/G', 'NOME', 'FRAÇÃO', 'JUSTIFICATIVA']], hide_index=True, use_container_width=True)
    else:
        st.success("Nenhuma falta registrada hoje.")
        
    st.markdown("---")
    st.subheader("📋 Histórico Completo de Registros (Logs)")
    st.dataframe(st.session_state.historico, hide_index=True, use_container_width=True)

# --- CONTROLE DE FLUXO DA APLICAÇÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    login()
else:
    # Menu lateral 
    with st.sidebar:
        st.markdown(f"👤 Logado como: **{st.session_state.usuario_atual.upper()}**")
        st.markdown(f"📍 Perfil: **{st.session_state.perfil}**")
        if st.button("🚪 Sair do Sistema"):
            st.session_state.logado = False
            st.rerun()
            
    # Roteamento de telas baseado no perfil
    if st.session_state.perfil == "CMT":
        tela_cmt()
    else:
        tela_sargento()