import os
import re
import json
import random
import threading
import hashlib
import io
import wave
import struct
import math
import webbrowser

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.animation import Animation
from kivy.network.urlrequest import UrlRequest
from kivy.graphics import Color, RoundedRectangle, Ellipse, Rectangle, Line

LabelBase.register(name='ChessFont', fn_regular='DejaVuSans.ttf')

SERVER_URL = "http://node.waifly.com:27402"
SITE_URL = "https://barabulka8xx-del.github.io/chess-site/" 
GAME_VERSION = "1.4.2"

# СЛОВАРИ ПЕРЕВОДОВ
LOCALES = {
    "ru": {
        "login_title": "Вход в аккаунт", "reg_title": "Регистрация",
        "login_btn": "Войти", "reg_btn": "Зарегистрироваться",
        "no_acc": "Нет аккаунта? Регистрация", "has_acc": "Уже есть аккаунт? Войти",
        "offline_btn": "Играть без интернета", "login_in": "Логин", "pass_in": "Пароль",
        "menu_title": "Шахматы", "elo": "Ваш ЭЛО:", "2p": "2 Игрока", "bot": "Игра с Ботом",
        "ranked": "Ранговый матч", "settings": "Настройки", "logout": "Выйти",
        "menu": "Меню", "undo": "Отмена", "no_undo": "Без отмены",
        "turn_w": "Ход белых", "turn_b": "Ход чёрных", "check": "ШАХ!",
        "thinking": "Бот думает...", "time": "Время:", "time_out": "Осталось:",
        "promo": "Выберите фигуру:", "back": "Назад", "diff_easy": "Легкий",
        "diff_med": "Средний", "diff_hard": "Сложный", "difficulty": "Сложность",
        "find_opp": "Найти соперника", "with_bot": "С Ботом", "searching": "Ищем соперника...\nПодождите.",
        "cancel_search": "Отменить поиск", "server_on": "сервер онлайн", "server_off": "сервер офлайн",
        "lang": "Язык / Language", "music": "Музыка", "music_vol": "Громкость музыки:",
        "music_off": "Музыка выключена", "apply": "Применить", "restart_req": "Язык изменен!\nПерейдите в меню для обновления.",
        "win": "ПОБЕДА!", "lose": "ПОРАЖЕНИЕ", "draw": "НИЧЬЯ"
    },
    "en": {
        "login_title": "Login", "reg_title": "Registration",
        "login_btn": "Login", "reg_btn": "Register",
        "no_acc": "No account? Register", "has_acc": "Have an account? Login",
        "offline_btn": "Play Offline", "login_in": "Login", "pass_in": "Password",
        "menu_title": "Chess", "elo": "Your ELO:", "2p": "2 Players", "bot": "Play vs Bot",
        "ranked": "Ranked Match", "settings": "Settings", "logout": "Logout",
        "menu": "Menu", "undo": "Undo", "no_undo": "No Undo",
        "turn_w": "White's turn", "turn_b": "Black's turn", "check": "CHECK!",
        "thinking": "Bot is thinking...", "time": "Time:", "time_out": "Left:",
        "promo": "Choose piece:", "back": "Back", "diff_easy": "Easy",
        "diff_med": "Medium", "diff_hard": "Hard", "difficulty": "Difficulty",
        "find_opp": "Find Opponent", "with_bot": "With Bot", "searching": "Searching for opponent...\nPlease wait.",
        "cancel_search": "Cancel Search", "server_on": "server online", "server_off": "server offline",
        "lang": "Language / Язык", "music": "Music", "music_vol": "Music Volume:",
        "music_off": "Music is off", "apply": "Apply", "restart_req": "Language changed!\nGo to menu to refresh.",
        "win": "VICTORY!", "lose": "DEFEAT", "draw": "DRAW"
    }
}

# ================== КАСТОМНЫЕ ЭЛЕМЕНТЫ UI ==================

class RoundedButton(Button):
    def __init__(self, **kwargs):
        bg_col = kwargs.pop('background_color', (0.4, 0.4, 0.4, 1))
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        with self.canvas.before:
            Color(0, 0, 0, 0.3) # Тень
            self.shadow = RoundedRectangle(pos=(self.x+2, self.y-2), size=self.size, radius=[dp(15)])
            Color(rgba=bg_col)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self.update_rect, size=self.update_rect)
        
    def update_rect(self, *args):
        self.shadow.pos = (self.x+3, self.y-3)
        self.shadow.size = self.size
        self.rect.pos = self.pos
        self.rect.size = self.size

class SquareButton(Button):
    def __init__(self, r, c, **kwargs):
        super().__init__(**kwargs)
        self.r = r
        self.c = c
        self.font_size = dp(32)
        self.font_name = 'ChessFont'
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        with self.canvas.before:
            self.sq_color = Color(rgba=(0.93, 0.84, 0.72, 1))
            self.sq_rect = Rectangle(pos=self.pos, size=self.size)
            self.dot_color = Color(0, 0, 0, 0)
            self.dot = Ellipse(size=(0, 0))
        self.bind(pos=self.update_graphics, size=self.update_graphics)
        
    def update_graphics(self, *args):
        self.sq_rect.pos = self.pos
        self.sq_rect.size = self.size
        dot_size = self.width * 0.25
        self.dot.size = (dot_size, dot_size)
        self.dot.pos = (self.center_x - dot_size/2, self.center_y - dot_size/2)
        
    def set_bg_color(self, color):
        self.sq_color.rgba = color
        
    def show_dot(self, visible):
        if visible:
            self.dot_color.rgba = (0, 0, 0, 0.5)
        else:
            self.dot_color.rgba = (0, 0, 0, 0)

# ================== ЛОГИКА ШАХМАТ ==================
KNIGHT_OFF = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
ORTHO = [(-1,0),(1,0),(0,-1),(0,1)]
DIAG  = [(-1,-1),(-1,1),(1,-1),(1,1)]

def inb(r, c): return 0 <= r < 8 and 0 <= c < 8

def start_state():
    return {'board': [['r','n','b','q','k','b','n','r'], ['p']*8, ['.']*8, ['.']*8, ['.']*8, ['.']*8, ['P']*8, ['R','N','B','Q','K','B','N','R']],
            'turn': 'w', 'castle_wk': True, 'castle_wq': True, 'castle_bk': True, 'castle_bq': True, 'ep': None, 'halfmove': 0}

def copy_state(s):
    return {'board': [row[:] for row in s['board']], 'turn': s['turn'], 'castle_wk': s['castle_wk'], 'castle_wq': s['castle_wq'],
            'castle_bk': s['castle_bk'], 'castle_bq': s['castle_bq'], 'ep': s['ep'], 'halfmove': s['halfmove']}

def is_attacked(b, r, c, by_white):
    for dr, dc in KNIGHT_OFF:
        nr, nc = r+dr, c+dc
        if inb(nr,nc):
            p = b[nr][nc]
            if by_white and p=='N': return True
            if not by_white and p=='n': return True
    if by_white:
        for dc in (-1,1):
            nr, nc = r+1, c+dc
            if inb(nr,nc) and b[nr][nc]=='P': return True
    else:
        for dc in (-1,1):
            nr, nc = r-1, c+dc
            if inb(nr,nc) and b[nr][nc]=='p': return True
    for dr, dc in ORTHO:
        nr, nc = r+dr, c+dc
        while inb(nr,nc):
            p = b[nr][nc]
            if p != '.':
                if by_white and p in 'RQ': return True
                if not by_white and p in 'rq': return True
                break
            nr += dr; nc += dc
    for dr, dc in DIAG:
        nr, nc = r+dr, c+dc
        while inb(nr,nc):
            p = b[nr][nc]
            if p != '.':
                if by_white and p in 'BQ': return True
                if not by_white and p in 'bq': return True
                break
            nr += dr; nc += dc
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            if dr==0 and dc==0: continue
            nr, nc = r+dr, c+dc
            if inb(nr,nc):
                p = b[nr][nc]
                if by_white and p=='K': return True
                if not by_white and p=='k': return True
    return False

def find_king(b, color):
    k = 'K' if color=='w' else 'k'
    for r in range(8):
        for c in range(8):
            if b[r][c] == k: return (r,c)
    return None

def in_check(s, color):
    kp = find_king(s['board'], color)
    return kp is not None and is_attacked(s['board'], kp[0], kp[1], color=='b')

def slide(b, r, c, turn, moves, dirs):
    for dr, dc in dirs:
        nr, nc = r+dr, c+dc
        while inb(nr,nc):
            t = b[nr][nc]
            if t == '.': moves.append((r,c,nr,nc,None,None))
            else:
                if (turn=='w' and t.islower()) or (turn=='b' and t.isupper()): moves.append((r,c,nr,nc,None,None))
                break
            nr += dr; nc += dc

def gen_pawn(b, r, c, turn, moves, ep):
    if turn=='w': fwd, start, promo = -1, 6, 0
    else: fwd, start, promo =  1, 1, 7
    nr = r + fwd
    if inb(nr, c) and b[nr][c] == '.':
        if nr == promo:
            for pr in 'QRBN': moves.append((r,c,nr,c,pr,None))
        else:
            moves.append((r,c,nr,c,None,None))
            if r == start:
                nr2 = r + 2*fwd
                if b[nr2][c] == '.': moves.append((r,c,nr2,c,None,None))
    for dc in (-1,1):
        nc = c+dc; nr = r+fwd
        if not inb(nr,nc): continue
        t = b[nr][nc]
        enemy = (turn=='w' and t.islower()) or (turn=='b' and t.isupper())
        if enemy:
            if nr == promo:
                for pr in 'QRBN': moves.append((r,c,nr,nc,pr,None))
            else: moves.append((r,c,nr,nc,None,None))
        elif ep and (nr,nc) == ep:
            moves.append((r,c,nr,nc,None,'ep'))

def gen_pseudo(s):
    b = s['board']; turn = s['turn']; ep = s['ep']; moves = []
    for r in range(8):
        for c in range(8):
            p = b[r][c]
            if p == '.': continue
            if turn=='w' and not p.isupper(): continue
            if turn=='b' and not p.islower(): continue
            k = p.upper()
            if k == 'P': gen_pawn(b, r, c, turn, moves, ep)
            elif k == 'N':
                for dr, dc in KNIGHT_OFF:
                    nr, nc = r+dr, c+dc
                    if inb(nr,nc):
                        t = b[nr][nc]
                        if (turn=='w' and (t=='.' or t.islower())) or (turn=='b' and (t=='.' or t.isupper())): moves.append((r,c,nr,nc,None,None))
            elif k == 'B': slide(b, r, c, turn, moves, DIAG)
            elif k == 'R': slide(b, r, c, turn, moves, ORTHO)
            elif k == 'Q': slide(b, r, c, turn, moves, DIAG+ORTHO)
            elif k == 'K':
                for dr in (-1,0,1):
                    for dc in (-1,0,1):
                        if dr==0 and dc==0: continue
                        nr, nc = r+dr, c+dc
                        if inb(nr,nc):
                            t = b[nr][nc]
                            if (turn=='w' and (t=='.' or t.islower())) or (turn=='b' and (t=='.' or t.isupper())): moves.append((r,c,nr,nc,None,None))
                if turn=='w' and (r,c)==(7,4):
                    if s['castle_wk'] and b[7][5]=='.' and b[7][6]=='.':
                        if not is_attacked(b,7,4,False) and not is_attacked(b,7,5,False) and not is_attacked(b,7,6,False): moves.append((7,4,7,6,None,'O-O'))
                    if s['castle_wq'] and b[7][1]=='.' and b[7][2]=='.' and b[7][3]=='.':
                        if not is_attacked(b,7,4,False) and not is_attacked(b,7,3,False) and not is_attacked(b,7,2,False): moves.append((7,4,7,2,None,'O-O-O'))
                if turn=='b' and (r,c)==(0,4):
                    if s['castle_bk'] and b[0][5]=='.' and b[0][6]=='.':
                        if not is_attacked(b,0,4,True) and not is_attacked(b,0,5,True) and not is_attacked(b,0,6,True): moves.append((0,4,0,6,None,'O-O'))
                    if s['castle_bq'] and b[0][1]=='.' and b[0][2]=='.' and b[0][3]=='.':
                        if not is_attacked(b,0,4,True) and not is_attacked(b,0,3,True) and not is_attacked(b,0,2,True): moves.append((0,4,0,2,None,'O-O-O'))
    return moves

def apply_move(s, m):
    ns = copy_state(s); b = ns['board']; fr, fc, tr, tc, promo, sp = m
    piece = b[fr][fc]; color = 'w' if piece.isupper() else 'b'; captured = b[tr][tc]
    
    if piece=='K': ns['castle_wk']=ns['castle_wq']=False
    if piece=='k': ns['castle_bk']=ns['castle_bq']=False
    if piece=='R':
        if (fr,fc)==(7,0): ns['castle_wq']=False
        if (fr,fc)==(7,7): ns['castle_wk']=False
    if piece=='r':
        if (fr,fc)==(0,0): ns['castle_bq']=False
        if (fr,fc)==(0,7): ns['castle_bk']=False
    if captured=='R':
        if (tr,tc)==(7,0): ns['castle_wq']=False
        if (tr,tc)==(7,7): ns['castle_wk']=False
    if captured=='r':
        if (tr,tc)==(0,0): ns['castle_bq']=False
        if (tr,tc)==(0,7): ns['castle_bk']=False
        
    ns['ep'] = None
    if piece.upper()=='P' and abs(tr-fr)==2: ns['ep'] = ((fr+tr)//2, fc)
    if sp=='ep':
        if color=='w': b[tr+1][tc] = '.'
        else: b[tr-1][tc] = '.'
        
    b[tr][tc] = promo if promo else piece
    b[fr][fc] = '.'
    
    if sp=='O-O':
        if color=='w': b[7][5]=b[7][7]; b[7][7]='.'
        else: b[0][5]=b[0][7]; b[0][7]='.'
    elif sp=='O-O-O':
        if color=='w': b[7][3]=b[7][0]; b[7][0]='.'
        else: b[0][3]=b[0][0]; b[0][0]='.'
        
    ns['turn'] = 'b' if color=='w' else 'w'
    pawn_or_cap = (piece.upper()=='P') or (captured != '.')
    ns['halfmove'] = 0 if pawn_or_cap else s['halfmove']+1
    return ns

def legal_moves(s):
    return [m for m in gen_pseudo(s) if not in_check(apply_move(s, m), s['turn'])]

def insufficient_material(b):
    pieces = []; bishop_colors = []
    for r in range(8):
        for c in range(8):
            p = b[r][c]
            if p != '.' and p.upper() != 'K': 
                pieces.append(p.lower())
                if p.lower() == 'b': bishop_colors.append((r + c) % 2)
    if len(pieces) == 0: return True
    if len(pieces) == 1 and pieces[0] in ['b', 'n']: return True
    if len(pieces) > 1 and all(p == 'b' for p in pieces):
        if len(set(bishop_colors)) == 1: return True
    return False

def game_status(s):
    if not legal_moves(s): return 'checkmate' if in_check(s, s['turn']) else 'stalemate'
    if s['halfmove'] >= 100: return 'draw50'
    if insufficient_material(s['board']): return 'draw_material'
    return None

# БОТ
PIECE_VAL = {'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000}
def evaluate_board(s):
    score = 0
    for r in range(8):
        for c in range(8):
            p = s['board'][r][c]
            if p != '.':
                val = PIECE_VAL[p.lower()]
                if p.isupper(): score += val
                else: score -= val
    return score

def minimax(s, depth, alpha, beta, maximizing):
    moves = legal_moves(s)
    if not moves: return -99999 if maximizing else 99999 if in_check(s, s['turn']) else 0
    if depth == 0: return evaluate_board(s)
    if maximizing:
        v = -float('inf')
        for m in moves:
            v = max(v, minimax(apply_move(s, m), depth-1, alpha, beta, False))
            alpha = max(alpha, v)
            if beta <= alpha: break
        return v
    else:
        v = float('inf')
        for m in moves:
            v = min(v, minimax(apply_move(s, m), depth-1, alpha, beta, True))
            beta = min(beta, v)
            if beta <= alpha: break
        return v

def get_bot_move(s, difficulty):
    moves = legal_moves(s)
    if not moves: return None
    if difficulty == 1: return random.choice(moves)
    best_move = moves[0]; best_val = float('inf')
    for m in moves:
        val = minimax(apply_move(s, m), 2, -float('inf'), float('inf'), True) + random.randint(-10, 10)
        if val < best_val: 
            best_val = val; best_move = m
    return best_move
    # ================== ЭКРАНЫ ПРИЛОЖЕНИЯ ==================

class LoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.12, 0.12, 0.12, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)
        
        main_layout = FloatLayout()
        self.bg_image = Image(source='icon.png', allow_stretch=True, keep_ratio=True, size_hint=(None, None), size=(dp(150), dp(150)), pos_hint={'center_x': 0.5, 'center_y': 0.6})
        main_layout.add_widget(self.bg_image)
        
        ui_layout = BoxLayout(orientation='vertical', size_hint=(1, 1), padding=dp(20))
        ui_layout.add_widget(Label(size_hint_y=0.85)) 
        self.status = Label(text="Загрузка...", font_size=dp(24), color=(1,1,1,1), size_hint_y=0.15)
        ui_layout.add_widget(self.status)
        main_layout.add_widget(ui_layout)
        self.add_widget(main_layout)
        
        self.anim = Animation(opacity=0.5, duration=1.0) + Animation(opacity=1.0, duration=1.0)
        self.anim.repeat = True
        self.anim.start(self.bg_image)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def go_next(self, dt):
        self.anim.stop(self.bg_image)
        app = App.get_running_app()
        self.manager.current = 'main_menu' if app.load_session() else 'login'     

class BackgroundScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_layout = FloatLayout()
        with self.canvas.before:
            Color(0.12, 0.12, 0.12, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)
        
        self.bg = Image(source='menu_bg.png', allow_stretch=True, keep_ratio=False, size_hint=(1, 1), pos_hint={'center_x': 0.5, 'center_y': 0.5}, opacity=0.15)
        self.main_layout.add_widget(self.bg)
        self.add_widget(self.main_layout)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class ChessBoard(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 8
        self.rows = 8
        self.squares = {}
        for r in range(8):
            for c in range(8):
                btn = SquareButton(r, c, text="")
                btn.bind(on_release=self.on_square_click)
                self.squares[(r,c)] = btn
                self.add_widget(btn)

    def on_square_click(self, instance):
        App.get_running_app().game_screen.handle_square_click(instance.r, instance.c)

    def update_board(self, state, selected, legal_targets, last_move):
        board = state['board']
        for (r, c), btn in self.squares.items():
            base_color = (0.93, 0.84, 0.72, 1) if (r+c)%2==0 else (0.71, 0.53, 0.39, 1)
            btn.set_bg_color(base_color)
            btn.text = ""
            btn.show_dot(False)
            
        piece_map = {'K':'♚','Q':'♛','R':'♜','B':'♝','N':'♞','P':'♟', 'k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}
        
        # Подсветка шаха
        if in_check(state, state['turn']):
            kp = find_king(board, state['turn'])
            if kp:
                self.squares[kp].set_bg_color((0.9, 0.2, 0.2, 1))

        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p != '.':
                    btn = self.squares[(r,c)]
                    btn.text = piece_map.get(p, p)
                    btn.color = (1, 1, 1, 1) if p.isupper() else (0, 0, 0, 1)

        if last_move:
            for rr, cc in (last_move[0:2], last_move[2:4]):
                self.squares[(rr,cc)].set_bg_color((0.8, 0.8, 0.4, 1))
                
        if selected:
            self.squares[selected].set_bg_color((0.96, 0.84, 0.43, 1))
            
        for m in legal_targets:
            self.squares[(m[2],m[3])].show_dot(True)

class LoginScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = 'login' 
        layout = BoxLayout(orientation='vertical', padding=dp(40), spacing=dp(10), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        
        self.title_label = Label(text="", font_size=dp(32), bold=True, size_hint_y=0.15)
        layout.add_widget(self.title_label)
        self.login_input = TextInput(hint_text="", multiline=False, size_hint_y=0.1, font_size=dp(20))
        layout.add_widget(self.login_input)
        self.pass_input = TextInput(hint_text="", password=True, multiline=False, size_hint_y=0.1, font_size=dp(20))
        layout.add_widget(self.pass_input)
        
        self.status_label = Label(text="", color=(1, 0.3, 0.3, 1), size_hint_y=0.1)
        layout.add_widget(self.status_label)
        
        self.submit_btn = RoundedButton(text="", size_hint_y=0.12, font_size=dp(20), background_color=(0.2, 0.6, 0.2, 1))
        self.submit_btn.bind(on_release=self.handle_submit)
        layout.add_widget(self.submit_btn)
        
        self.toggle_btn = RoundedButton(text="", size_hint_y=0.1, font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        self.toggle_btn.bind(on_release=self.toggle_mode)
        layout.add_widget(self.toggle_btn)
        
        self.offline_btn = RoundedButton(text="", size_hint_y=0.1, font_size=dp(16), background_color=(0.5, 0.3, 0.1, 1))
        self.offline_btn.bind(on_release=self.play_offline)
        layout.add_widget(self.offline_btn)
        
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        app.play_music()
        self.update_translations()

    def update_translations(self):
        app = App.get_running_app()
        self.title_label.text = app.t("login_title") if self.mode == 'login' else app.t("reg_title")
        self.submit_btn.text = app.t("login_btn") if self.mode == 'login' else app.t("reg_btn")
        self.toggle_btn.text = app.t("no_acc") if self.mode == 'login' else app.t("has_acc")
        self.offline_btn.text = app.t("offline_btn")
        self.login_input.hint_text = app.t("login_in")
        self.pass_input.hint_text = app.t("pass_in")

    def play_offline(self, instance):
        app = App.get_running_app()
        app.is_offline = True
        app.current_user = "Гость"
        app.player_elo = 0
        app.logout_session() 
        self.manager.current = 'main_menu'

    def toggle_mode(self, instance):
        self.mode = 'register' if self.mode == 'login' else 'login'
        self.status_label.text = ""
        self.login_input.text = ""
        self.pass_input.text = ""
        self.update_translations()

    def handle_submit(self, instance):
        login = self.login_input.text.strip()
        password = self.pass_input.text.strip()
        if not login or not password:
            self.status_label.text = "Заполните все поля!"
            return
        self.status_label.text = "Подключение..."
        self.status_label.color = (1, 1, 0, 1)
        self.submit_btn.disabled = True 
        app = App.get_running_app()
        app.is_offline = False
        req_body = json.dumps({"login": login, "password": password})
        req_headers = {'Content-Type': 'application/json'}

        if self.mode == 'login':
            def on_success(req, result):
                self.submit_btn.disabled = False
                app.current_user = login
                app.player_elo = result.get('elo', 300) 
                app.save_session()
                self.manager.current = 'main_menu'
            def on_error(req, error):
                self.submit_btn.disabled = False
                self.status_label.color = (1, 0.3, 0.3, 1)
                self.status_label.text = "ВЫ ЗАБАНЕНЫ!" if req.resp_status == 403 else "Неверный пароль"
            UrlRequest(f"{SERVER_URL}/login", req_body=req_body, req_headers=req_headers, on_success=on_success, on_error=on_error, on_failure=on_error, timeout=10)
        else:
            def on_success(req, result):
                self.submit_btn.disabled = False
                self.status_label.color = (0, 1, 0, 1)
                self.status_label.text = "Успешно! Войдите."
                self.toggle_mode(None) 
            def on_error(req, error):
                self.submit_btn.disabled = False
                self.status_label.color = (1, 0.3, 0.3, 1)
                self.status_label.text = "Логин занят!"
            UrlRequest(f"{SERVER_URL}/register", req_body=req_body, req_headers=req_headers, on_success=on_success, on_error=on_error, on_failure=on_error, timeout=10)

class MainMenuScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ui_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(8), size_hint=(0.8, 0.95), pos_hint={'center_x': 0.5, 'center_y': 0.45})
        
        self.user_label = Label(text="", font_size=dp(18), color=(1, 1, 1, 1), size_hint_y=0.08)
        ui_layout.add_widget(self.user_label)
        self.title_lbl = Label(text="", font_size=dp(36), bold=True, size_hint_y=0.12)
        ui_layout.add_widget(self.title_lbl)
        self.elo_label = Label(text="", font_size=dp(22), color=(1, 0.8, 0.2, 1), size_hint_y=0.08)
        ui_layout.add_widget(self.elo_label)
        
        self.btn_2p = RoundedButton(text="", font_size=dp(20), size_hint_y=0.11, background_color=(0.2, 0.6, 0.2, 1))
        self.btn_2p.bind(on_release=lambda x: setattr(self.manager, 'current', 'two_players_menu'))
        ui_layout.add_widget(self.btn_2p)
        
        self.btn_bot = RoundedButton(text="", font_size=dp(20), size_hint_y=0.11, background_color=(0.8, 0.5, 0.2, 1))
        self.btn_bot.bind(on_release=lambda x: self.start_bot_menu())
        ui_layout.add_widget(self.btn_bot)
        
        self.btn_ranked = RoundedButton(text="", font_size=dp(20), size_hint_y=0.11, background_color=(0.2, 0.5, 0.8, 1))
        self.btn_ranked.bind(on_release=lambda x: self.start_ranked())
        ui_layout.add_widget(self.btn_ranked)
        
        self.admin_btn = RoundedButton(text="Отправить уведомление", font_size=dp(14), size_hint_y=0.08, background_color=(0.8, 0.2, 0.8, 1))
        self.admin_btn.bind(on_release=self.show_admin_panel)
        ui_layout.add_widget(self.admin_btn)
        
        btn_layout = BoxLayout(size_hint_y=0.1, spacing=dp(10))
        self.btn_settings = RoundedButton(text="⚙️", font_size=dp(20), background_color=(0.4, 0.4, 0.4, 1))
        self.btn_settings.bind(on_release=lambda x: setattr(self.manager, 'current', 'settings'))
        btn_layout.add_widget(self.btn_settings)
        
        self.btn_logout = RoundedButton(text="", font_size=dp(14), background_color=(0.5, 0.2, 0.2, 1))
        self.btn_logout.bind(on_release=self.logout)
        btn_layout.add_widget(self.btn_logout)
        ui_layout.add_widget(btn_layout)
        
        ui_layout.add_widget(Label(text=f"v{GAME_VERSION}", font_size=dp(10), color=(0.5, 0.5, 0.5, 1), size_hint_y=0.05))
        
        self.main_layout.add_widget(ui_layout)

        self.info_btn = RoundedButton(text="(i)", font_size=dp(20), bold=True, size_hint=(None, None), size=(dp(50), dp(50)), pos_hint={'right': 0.95, 'y': 0.05}, background_color=(0.2, 0.5, 0.8, 1))
        self.info_btn.bind(on_release=self.show_changelog)
        self.main_layout.add_widget(self.info_btn)

        self.dl_btn = RoundedButton(text="▶", font_size=dp(22), font_name='ChessFont', size_hint=(None, None), size=(dp(50), dp(50)), pos_hint={'right': 0.78, 'y': 0.05}, background_color=(0.8, 0.2, 0.8, 1))
        self.dl_btn.bind(on_release=lambda x: webbrowser.open(SITE_URL)) 
        self.dl_btn.opacity = 0
        self.dl_btn.disabled = True
        self.main_layout.add_widget(self.dl_btn)

    def update_translations(self):
        app = App.get_running_app()
        self.title_lbl.text = app.t("menu_title")
        self.btn_2p.text = app.t("2p")
        self.btn_bot.text = app.t("bot")
        self.btn_ranked.text = app.t("ranked")
        self.btn_logout.text = app.t("logout")

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        self.update_translations()
        self.user_label.text = f"{app.current_user}"
        
        if app.current_user == "DEV$DEV":
            self.admin_btn.opacity = 1
            self.admin_btn.disabled = False
        else:
            self.admin_btn.opacity = 0
            self.admin_btn.disabled = True

        if app.is_offline:
            self.elo_label.text = f"{app.t('elo')} Офлайн"
        else:
            def sync_success(req, result):
                app.player_elo = result.get('elo', app.player_elo)
                app.save_user_data()
                self.elo_label.text = f"{app.t('elo')} {app.player_elo}"
                warning = result.get('warning')
                if warning: self.show_warning(warning)
            def sync_fail(req, error):
                self.elo_label.text = f"{app.t('elo')} {app.player_elo}"
            
            if app.current_user:
                UrlRequest(f"{SERVER_URL}/sync_elo/{app.current_user}", on_success=sync_success, on_error=sync_fail, on_failure=sync_fail)
            
            def version_success(req, result):
                try:
                    server_ver = str(json.loads(result).get('version', '1.0') if isinstance(result, str) else result.get('version', '1.0'))
                    if server_ver != str(GAME_VERSION):
                        self.dl_btn.opacity = 1
                        self.dl_btn.disabled = False
                    else:
                        self.dl_btn.opacity = 0
                        self.dl_btn.disabled = True
                except: pass
            UrlRequest(f"{SERVER_URL}/get_version", on_success=version_success)
        app.play_music()

    def show_warning(self, warning):
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(15))
        lbl = Label(text=warning, halign="center", font_size=dp(16))
        content.add_widget(lbl)
        popup = Popup(title="Внимание!", content=content, size_hint=(0.85, 0.4), auto_dismiss=False)
        btn = RoundedButton(text="Понятно", size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.2, 1))
        btn.bind(on_release=lambda x: [popup.dismiss(), UrlRequest(f"{SERVER_URL}/acknowledge_warning/{App.get_running_app().current_user}")])
        content.add_widget(btn)
        popup.open()

    def show_changelog(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        scroll = ScrollView()
        layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(15))
        layout.bind(minimum_height=layout.setter('height'))
        
        layout.add_widget(Label(text="[b][color=f1c40f]История обновлений[/color][/b]", markup=True, font_size=dp(22), size_hint_y=None, height=dp(50)))
        
        log_text = (
            "[b]Обновление 7[/b]\n"
            "• Глобальное обновление интерфейса!\n"
            "• Добавлены настройки: выбор языка (RU/EN) и громкость музыки.\n"
            "• Клетка короля теперь подсвечивается красным при шахе.\n"
            "• Добавлена вибрация при ходе (на телефонах).\n"
            "• Окно превращения пешки стало красивее.\n"
            "• Проведена оптимизация подсистем сборки.\n\n"
            "[b]Обновление 6[/b]\n"
            "• Добавлена история последних матчей.\n"
            "• Улучшена стабильность игры.\n\n"
            "[b]Обновление 5[/b]\n"
            "• На сайте появилась защита от спама.\n"
            "• В чате поддержки теперь видны имена.\n\n"
            "[b]Обновление 4[/b]\n"
            "• Переработан дизайн игры в стиле сайта.\n"
            "• Фон меню затемнен, кнопки читаются лучше.\n\n"
            "[b]Обновление 3[/b]\n"
            "• Убран штраф за выход из дружеской игры.\n"
            "• Уведомления больше не спамят.\n\n"
            "[b]Обновление 2[/b]\n"
            "• Исправлены вылеты при запуске.\n"
            "• Добавлена ничья при нехватке фигур.\n\n"
            "[b]Обновление 1[/b]\n"
            "• Самый первый релиз игры.\n"
        )
        lbl = Label(text=log_text, markup=True, halign="left", valign="top", font_size=dp(15), size_hint_y=None)
        lbl.bind(width=lambda instance, value: setattr(instance, 'text_size', (value, None)))
        lbl.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        layout.add_widget(lbl)
        
        scroll.add_widget(layout)
        content.add_widget(scroll)
        
        btn_close = RoundedButton(text="Закрыть", size_hint_y=None, height=dp(50), background_color=(0.8, 0.2, 0.2, 1))
        popup = Popup(title="О игре", content=content, size_hint=(0.9, 0.8))
        btn_close.bind(on_release=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()

    def start_bot_menu(self):
        App.get_running_app().is_ranked = False
        self.manager.current = 'bot_menu'

    def start_ranked(self):
        if App.get_running_app().is_offline:
            Popup(title="Офлайн", content=Label(text="Ранговые матчи недоступны\nбез интернета."), size_hint=(0.8, 0.3)).open()
            return
        self.manager.current = 'ranked_menu'

    def logout(self, instance):
        app = App.get_running_app()
        app.current_user = None
        app.player_elo = 300
        app.is_offline = False
        app.logout_session()
        self.manager.current = 'login'

    def show_admin_panel(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
        input_text = TextInput(hint_text="Текст уведомления...", multiline=False, size_hint_y=None, height=dp(50))
        content.add_widget(input_text)
        pass_input = TextInput(hint_text="Пароль", password=True, multiline=False, size_hint_y=None, height=dp(50))
        content.add_widget(pass_input)
        
        popup = Popup(title="Рассылка", content=content, size_hint=(0.8, 0.5))
        btn_layout = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(50))
        
        def send_notification(req_inst):
            pwd = pass_input.text.strip()
            if not input_text.text.strip() or not pwd: return
            req_body = json.dumps({"login": "DEV$DEV", "password": pwd, "message": input_text.text.strip()})
            def on_success(req, res):
                popup.dismiss()
                Popup(title="Успех", content=Label(text="Отправлено!"), size_hint=(0.8, 0.3)).open()
            UrlRequest(f"{SERVER_URL}/admin/send_update", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=on_success, on_error=lambda r,e: Popup(title="Ошибка", content=Label(text="Неверный пароль"), size_hint=(0.8, 0.3)).open())
        
        btn_send = RoundedButton(text="Отправить", background_color=(0.2, 0.6, 0.2, 1))
        btn_send.bind(on_release=send_notification)
        btn_layout.add_widget(btn_send)
        content.add_widget(btn_layout)
        popup.open()

class SettingsScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(40), spacing=dp(20), size_hint=(0.9, 0.8), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        
        self.title_lbl = Label(text="", font_size=dp(30), bold=True, size_hint_y=0.15)
        layout.add_widget(self.title_lbl)
        
        self.lang_btn = RoundedButton(text="", font_size=dp(18), size_hint_y=0.15, background_color=(0.2, 0.5, 0.8, 1))
        self.lang_btn.bind(on_release=self.switch_lang)
        layout.add_widget(self.lang_btn)
        
        self.music_lbl = Label(text="", font_size=dp(16), size_hint_y=0.1)
        layout.add_widget(self.music_lbl)
        
        self.vol_slider = Slider(min=0, max=1, value=0.3, size_hint_y=0.15)
        self.vol_slider.bind(value=self.change_volume)
        layout.add_widget(self.vol_slider)
        
        btn_back = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.5, 0.2, 0.2, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'main_menu'))
        layout.add_widget(btn_back)
        self.btn_back = btn_back
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        self.update_translations()
        self.vol_slider.value = App.get_running_app().music_volume

    def update_translations(self):
        app = App.get_running_app()
        self.title_lbl.text = app.t("settings")
        self.lang_btn.text = f"{app.t('lang')}: {'Русский' if app.lang == 'ru' else 'English'}"
        self.music_lbl.text = f"{app.t('music_vol')} {int(self.vol_slider.value * 100)}%"
        self.btn_back.text = app.t("back")

    def switch_lang(self, instance):
        app = App.get_running_app()
        app.lang = 'en' if app.lang == 'ru' else 'ru'
        app.save_settings()
        self.update_translations()

    def change_volume(self, instance, value):
        app = App.get_running_app()
        app.music_volume = value
        if app.bg_music:
            app.bg_music.volume = value
        self.music_lbl.text = f"{app.t('music_vol')} {int(value * 100)}%"
        app.save_settings()

class TwoPlayersMenuScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.title_lbl = Label(text="", font_size=dp(30), bold=True, size_hint_y=0.2)
        layout.add_widget(self.title_lbl)
        self.btn_local = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.6, 0.2, 1))
        self.btn_local.bind(on_release=self.start_local)
        layout.add_widget(self.btn_local)
        self.btn_online = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.5, 0.8, 1))
        self.btn_online.bind(on_release=self.show_room_menu)
        layout.add_widget(self.btn_online)
        self.btn_back = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.5, 0.2, 0.2, 1))
        self.btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'main_menu'))
        layout.add_widget(self.btn_back)
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        App.get_running_app().play_music()
        app = App.get_running_app()
        self.title_lbl.text = app.t("2p")
        self.btn_local.text = app.t("2p") 
        self.btn_online.text = "Онлайн по коду" if app.lang == 'ru' else "Online by code"
        self.btn_back.text = app.t("back")

    def start_local(self, instance):
        app = App.get_running_app()
        app.is_ranked = False
        app.is_online = False
        app.game_mode = '2p'
        app.game_screen.new_game()
        self.manager.current = 'game'

    def show_room_menu(self, instance):
        app = App.get_running_app()
        if app.is_offline:
            Popup(title="Офлайн", content=Label(text="Нет интернета"), size_hint=(0.8, 0.3)).open()
            return

        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
        btn_create = RoundedButton(text="Создать", size_hint_y=None, height=dp(50), background_color=(0.2, 0.7, 0.2, 1))
        btn_join = RoundedButton(text="Войти", size_hint_y=None, height=dp(50), background_color=(0.2, 0.5, 0.8, 1))
        code_input = TextInput(hint_text="Код", multiline=False, size_hint_y=None, height=dp(50))
        content.add_widget(btn_create)
        content.add_widget(code_input)
        content.add_widget(btn_join)
        popup = Popup(title="Онлайн", content=content, size_hint=(0.8, 0.5))
        
        def create_req(req, result):
            popup.dismiss()
            self.waiting_popup = Popup(title="Комната", content=Label(text=f"Код: {result['room_id']}\nЖдем..."), size_hint=(0.8, 0.4), auto_dismiss=False)
            self.waiting_popup.open()
            self.poll_join(result['room_id'])

        def join_req(req, result):
            popup.dismiss()
            app.is_online = True
            app.is_ranked = False
            app.online_room_id = code_input.text.strip().upper()
            app.online_color = 'black'
            app.online_opponent = result.get('opponent', 'Соперник')
            app.game_screen.new_game()
            self.manager.current = 'game'

        btn_create.bind(on_release=lambda x: UrlRequest(f"{SERVER_URL}/create_room", req_body=json.dumps({"login": app.current_user}), req_headers={'Content-Type': 'application/json'}, on_success=create_req))
        btn_join.bind(on_release=lambda x: UrlRequest(f"{SERVER_URL}/join_room", req_body=json.dumps({"login": app.current_user, "room_code": code_input.text.strip().upper()}), req_headers={'Content-Type': 'application/json'}, on_success=join_req))
        popup.open()

    def poll_join(self, room_id):
        app = App.get_running_app()
        def check(req, result):
            if result.get('players_count', 0) >= 2 or result.get('board_data') is not None:
                self.waiting_popup.dismiss()
                app.is_online = True
                app.is_ranked = False
                app.online_room_id = room_id
                app.online_color = 'white'
                app.game_screen.new_game()
                self.manager.current = 'game'
            else: Clock.schedule_once(lambda dt: self.poll_join(room_id), 2)
        UrlRequest(f"{SERVER_URL}/get_move/{room_id}", on_success=check, on_failure=lambda r, e: Clock.schedule_once(lambda dt: self.poll_join(room_id), 3))

class RankedMenuScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.title_lbl = Label(text="", font_size=dp(30), bold=True, size_hint_y=0.2)
        layout.add_widget(self.title_lbl)
        self.btn_find = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.6, 0.8, 1))
        self.btn_find.bind(on_release=self.find_online_match)
        layout.add_widget(self.btn_find)
        self.btn_bot = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.6, 0.2, 1))
        self.btn_bot.bind(on_release=self.start_ranked_bot)
        layout.add_widget(self.btn_bot)
        self.btn_back = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.5, 0.2, 0.2, 1))
        self.btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'main_menu'))
        layout.add_widget(self.btn_back)
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        app.play_music()
        self.title_lbl.text = app.t("ranked")
        self.btn_find.text = app.t("find_opp")
        self.btn_bot.text = app.t("with_bot")
        self.btn_back.text = app.t("back")

    def find_online_match(self, instance):
        app = App.get_running_app()
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text=app.t("searching")))
        btn_cancel = RoundedButton(text=app.t("cancel_search"), size_hint_y=None, height=dp(50), background_color=(0.8, 0.2, 0.2, 1))
        content.add_widget(btn_cancel)
        self.waiting_popup = Popup(title="Поиск", content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
        btn_cancel.bind(on_release=lambda x: [setattr(self, 'is_searching', False), self.waiting_popup.dismiss()])
        self.waiting_popup.open()
        self.is_searching = True
        self.do_search(app)

    def do_search(self, app):
        if not self.is_searching: return
        def on_success(req, result):
            if not self.is_searching: return
            if result.get('status') == 'matched':
                self.is_searching = False
                self.waiting_popup.dismiss()
                app.is_online = True
                app.is_ranked = True
                app.online_room_id = result['room_id']
                app.online_color = result['color']
                app.online_opponent = result['opponent']
                app.online_opponent_elo = result.get('opponent_elo', 300)
                app.game_screen.new_game()
                self.manager.current = 'game'
            else:
                Clock.schedule_once(lambda dt: self.do_search(app), 2)
        req_body = json.dumps({"login": app.current_user, "elo": app.player_elo, "version": GAME_VERSION})
        UrlRequest(f"{SERVER_URL}/find_match", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=on_success, on_failure=lambda r, e: Clock.schedule_once(lambda dt: self.do_search(app), 3))

    def start_ranked_bot(self, instance):
        app = App.get_running_app()
        elo = app.player_elo
        diff = 1 if elo <= 450 else 2 if elo <= 1000 else 3
        app.is_ranked = True
        app.is_online = False
        app.game_mode = 'bot'
        app.bot_diff = diff
        app.game_screen.new_game()
        self.manager.current = 'game'

class BotMenuScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.title_lbl = Label(text="", font_size=dp(30), size_hint_y=0.3)
        layout.add_widget(self.title_lbl)
        self.btns = []
        for diff in range(1, 4):
            btn = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.5, 0.8, 1))
            btn.bind(on_release=lambda x, d=diff: self.start_bot(d))
            layout.add_widget(btn)
            self.btns.append(btn)
        self.btn_back = RoundedButton(text="", font_size=dp(20), size_hint_y=0.15, background_color=(0.5, 0.2, 0.2, 1))
        self.btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'main_menu'))
        layout.add_widget(self.btn_back)
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        app.play_music()
        self.title_lbl.text = app.t("difficulty")
        self.btns[0].text = app.t("diff_easy")
        self.btns[1].text = app.t("diff_med")
        self.btns[2].text = app.t("diff_hard")
        self.btn_back.text = app.t("back")

    def start_bot(self, diff):
        app = App.get_running_app()
        app.is_ranked = False
        app.is_online = False
        app.game_mode = 'bot'
        app.bot_diff = diff
        app.game_screen.new_game()
        self.manager.current = 'game'

class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = start_state() 
        self.history = []          
        self.selected = None       
        self.legal_targets = []    
        self.last_move = None      
        self.bot_thinking = False  
        self.game_over_triggered = False 
        self.time_left = 45
        self.timer_event = None
        self.poll_event = None
        
        main_layout = BoxLayout(orientation='vertical')
        top_bar = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(5), padding=dp(5))
        
        self.btn_menu = RoundedButton(text="", font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        self.btn_menu.bind(on_release=self.go_to_menu)
        top_bar.add_widget(self.btn_menu)
        
        self.status_label = Label(text="", font_size=dp(16), bold=True)
        top_bar.add_widget(self.status_label)
        
        self.timer_label = Label(text="", font_size=dp(18), bold=True, color=(1, 0.5, 0.5, 1))
        top_bar.add_widget(self.timer_label)
        
        self.btn_undo = RoundedButton(text="", font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        self.btn_undo.bind(on_release=self.undo_move)
        top_bar.add_widget(self.btn_undo)
        main_layout.add_widget(top_bar)
        
        board_container = FloatLayout()
        self.board_ui = ChessBoard(size_hint=(0.95, None), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.board_ui.bind(width=lambda instance, value: setattr(instance, 'height', value))
        board_container.add_widget(self.board_ui)
        main_layout.add_widget(board_container)
        self.add_widget(main_layout)

    def on_pre_enter(self, *args):
        App.get_running_app().stop_music()
        app = App.get_running_app()
        self.btn_menu.text = app.t("menu")
        if app.game_mode == 'bot' and not app.is_ranked:
            self.btn_undo.text = app.t("undo")
        else:
            self.btn_undo.text = app.t("no_undo")

    def on_leave(self, *args):
        self.stop_timer()
        self.stop_polling()

    def new_game(self):
        self.state = start_state()
        self.history = []
        self.selected = None
        self.legal_targets = []
        self.last_move = None
        self.bot_thinking = False
        self.game_over_triggered = False
        app = App.get_running_app()
        
        if app.is_ranked:
            app.save_active_game(True) 
            self.reset_timer()
        else:
            app.save_active_game(False)
            self.stop_timer()
            self.timer_label.text = "" 
            
        if app.is_online: self.start_polling() 
        self.update_ui()

    def start_polling(self):
        self.stop_polling()
        self.poll_event = Clock.schedule_interval(self.check_server_move, 1.5)

    def stop_polling(self):
        if self.poll_event:
            self.poll_event.cancel()
            self.poll_event = None

    def check_server_move(self, dt):
        app = App.get_running_app()
        if not app.is_online or not app.online_room_id: return
        def on_success(req, result):
            if not result or not result.get('board_data'): return
            new_state = json.loads(result['board_data'])
            if self.state['turn'] != new_state['turn'] or self.state['board'] != new_state['board']:
                self.history.append((copy_state(self.state), self.last_move))
                self.state = new_state
                self.last_move = None
                self.selected = None
                self.legal_targets = []
                app.play_sound()
                self.update_ui()
                if app.is_ranked: self.reset_timer()
        def on_fail(req, error):
            if getattr(req, 'resp_status', None) == 404:
                self.stop_polling()
                self.stop_timer()
                if self.game_over_triggered: return
                self.game_over_triggered = True
                self.show_end_popup(app.t("win"), "Соперник покинул игру.")
        UrlRequest(f"{SERVER_URL}/get_move/{app.online_room_id}", on_success=on_success, on_error=on_fail, on_failure=on_fail)

    def start_timer(self):
        self.stop_timer()
        app = App.get_running_app()
        if not (app.is_ranked or app.is_online): return
        my_color = 'w' if not hasattr(app, 'online_color') else ('w' if app.online_color == 'white' else 'b')
        if self.state['turn'] != my_color: return
        self.timer_event = Clock.schedule_interval(self.tick_timer, 1)

    def stop_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def tick_timer(self, dt):
        if game_status(self.state) is not None or self.time_left <= 0:
            self.stop_timer()
            if self.time_left <= 0: self.time_out_loss()
            return
        self.time_left -= 1
        self.timer_label.text = f"{App.get_running_app().t('time')} {self.time_left}"

    def reset_timer(self):
        self.time_left = 45
        self.start_timer()

    def time_out_loss(self):
        self.game_over_triggered = True
        app = App.get_running_app()
        app.save_active_game(False)
        if app.is_ranked:
            penalty = app.calculate_loss_penalty()
            app.player_elo = max(0, app.player_elo - penalty)
            app.save_user_data()
            self.show_end_popup(app.t("lose"), f"Время вышло! -{penalty} ЭЛО")
        else: 
            self.show_end_popup("Время", "Время вышло!")

    def update_ui(self):
        self.board_ui.update_board(self.state, self.selected, self.legal_targets, self.last_move)
        app = App.get_running_app()
        if self.bot_thinking: self.status_label.text = app.t("thinking")
        elif game_status(self.state) == 'checkmate': self.status_label.text = "МАТ!"
        elif in_check(self.state, self.state['turn']): self.status_label.text = app.t("check")
        else: self.status_label.text = app.t("turn_w") if self.state['turn'] == 'w' else app.t("turn_b")
        self.check_game_over()

    def check_game_over(self):
        st = game_status(self.state)
        if st and not self.game_over_triggered:
            self.game_over_triggered = True
            self.stop_timer()
            self.stop_polling()
            app = App.get_running_app()
            app.save_active_game(False)
            if st == 'checkmate':
                title = app.t("win") if self.state['turn'] == 'b' else app.t("lose")
                if app.game_mode == '2p': title = "МАТ!"
                self.show_end_popup(title, "Игра окончена.")
            else:
                self.show_end_popup(app.t("draw"), "Ничья.")

    def show_end_popup(self, title, text):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text=text, halign="center", font_size=dp(18)))
        btn = RoundedButton(text="OK", size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.2, 1))
        content.add_widget(btn)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
        btn.bind(on_release=lambda x: [popup.dismiss(), setattr(self.manager, 'current', 'main_menu')])
        popup.open()

    def go_to_menu(self, instance):
        self.stop_timer()
        self.stop_polling()
        self.manager.current = 'main_menu'

    def undo_move(self, instance):
        app = App.get_running_app()
        if app.is_ranked or app.is_online: return
        if game_status(self.state) is not None: return
        if self.history:
            self.state, self.last_move = self.history.pop()
            if app.game_mode == 'bot' and self.state['turn'] == 'b' and self.history:
                self.state, self.last_move = self.history.pop()
        self.selected = None
        self.legal_targets = []
        self.update_ui()

    def handle_square_click(self, r, c):
        if game_status(self.state) is not None: return
        app = App.get_running_app()
        if app.is_online:
            my_color = 'w' if app.online_color == 'white' else 'b'
            if self.state['turn'] != my_color: return
        if app.game_mode == 'bot' and not app.is_online and (self.bot_thinking or self.state['turn'] == 'b'): return
        
        if self.selected:
            for m in self.legal_targets:
                if (m[2], m[3]) == (r, c):
                    if m[4]: 
                        self.show_promotion(m)
                        return
                    self.make_move(m)
                    return
        p = self.state['board'][r][c]
        turn = self.state['turn']
        if p != '.' and ((turn=='w' and p.isupper()) or (turn=='b' and p.islower())):
            self.selected = (r, c)
            self.legal_targets = [m for m in legal_moves(self.state) if (m[0],m[1]) == (r, c)]
        else:
            self.selected = None
            self.legal_targets = []
        self.update_ui()

    def show_promotion(self, m):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text=App.get_running_app().t("promo")))
        btn_layout = BoxLayout(spacing=dp(10))
        for pr, sym in [('Q', '♛'), ('R', '♜'), ('B', '♝'), ('N', '♞')]:
            btn = RoundedButton(text=sym, font_size=dp(40), font_name='ChessFont', background_color=(0.2, 0.5, 0.8, 1))
            btn.bind(on_release=lambda x, p=pr: self.finish_promotion(m, p))
            btn_layout.add_widget(btn)
        content.add_widget(btn_layout)
        self.popup = Popup(title="", content=content, size_hint=(0.8, 0.4))
        self.popup.open()

    def finish_promotion(self, m, pr):
        self.popup.dismiss()
        self.make_move((m[0], m[1], m[2], m[3], pr, m[5]))

    def make_move(self, m):
        self.history.append((copy_state(self.state), self.last_move))
        self.state = apply_move(self.state, m)
        self.last_move = m
        self.selected = None
        self.legal_targets = []
        app = App.get_running_app()
        self.stop_timer()
        app.play_sound()
        app.vibrate() # ВИБРАЦИЯ
        
        if app.is_online:
            UrlRequest(f"{SERVER_URL}/make_move", req_body=json.dumps({
                "room_id": app.online_room_id, "login": app.current_user, "board_data": json.dumps(self.state) 
            }), req_headers={'Content-Type': 'application/json'}, on_failure=lambda r, e: None)
            
        self.update_ui()
        if not app.is_online and app.game_mode == 'bot' and game_status(self.state) is None and self.state['turn'] == 'b':
            self.start_bot()
        elif app.is_online and app.is_ranked:
            self.reset_timer()

    def start_bot(self):
        self.bot_thinking = True
        app = App.get_running_app()
        app.bot_gen += 1
        my_gen = app.bot_gen
        s_copy = copy_state(self.state)
        def compute():
            m = get_bot_move(s_copy, app.bot_diff)
            Clock.schedule_once(lambda dt: self.apply_bot(m, my_gen))
        threading.Thread(target=compute, daemon=True).start()

    def apply_bot(self, m, gen):
        app = App.get_running_app()
        if gen != app.bot_gen: return
        self.bot_thinking = False
        if m:
            if m[4]: m = (m[0], m[1], m[2], m[3], 'Q', m[5])
            self.history.append((copy_state(self.state), self.last_move))
            self.state = apply_move(self.state, m)
            self.last_move = m
            app.play_sound()
        if app.is_ranked: self.reset_timer()
        self.update_ui()

class ChessApp(App):
    game_mode = '2p'
    bot_diff = 1
    bot_gen = 0
    sound_move = None
    bg_music = None
    
    current_user = None
    player_elo = 300
    is_ranked = False
    is_online = False
    is_offline = False
    online_room_id = None
    online_color = 'white'
    online_opponent = None
    online_opponent_elo = 300
    
    lang = 'ru' 
    music_volume = 0.3

    def build(self):
        self.load_settings()
        self.init_audio()
        sm = ScreenManager()
        sm.add_widget(LoadingScreen(name='loading'))
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(MainMenuScreen(name='main_menu'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(TwoPlayersMenuScreen(name='two_players_menu'))
        sm.add_widget(BotMenuScreen(name='bot_menu'))
        sm.add_widget(RankedMenuScreen(name='ranked_menu'))
        
        self.game_screen = GameScreen(name='game')
        sm.add_widget(self.game_screen)
        
        sm.current = 'loading'
        Clock.schedule_once(lambda dt: sm.get_screen('loading').go_next(None), 2)
        return sm

    def t(self, key):
        return LOCALES.get(self.lang, LOCALES['ru']).get(key, key)

    def load_settings(self):
        path = os.path.join(self.user_data_dir, 'settings.json')
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.lang = data.get('lang', 'ru')
                    self.music_volume = data.get('volume', 0.3)
            except: pass

    def save_settings(self):
        path = os.path.join(self.user_data_dir, 'settings.json')
        try:
            with open(path, 'w') as f:
                json.dump({'lang': self.lang, 'volume': self.music_volume}, f)
        except: pass

    def vibrate(self):
        try:
            from jnius import autoclass
            Context = autoclass('android.content.Context')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            vibrator = PythonActivity.mActivity.getSystemService(Context.VIBRATOR_SERVICE)
            if vibrator.hasVibrator():
                vibrator.vibrate(50) # 50 миллисекунд
        except:
            pass # На ПК вибрации нет

    def init_audio(self):
        path = "beep.wav"
        if not os.path.exists(path):
            try:
                sample_rate = 16000
                n = int(sample_rate * 0.08)
                buf = io.BytesIO()
                with wave.open(buf, 'wb') as wf:
                    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
                    frames = bytearray(n * 2)
                    for i in range(n):
                        env = min(1.0, i / 200) * min(1.0, (n - i) / 200)
                        v = int(32767 * 0.2 * env * math.sin(2 * math.pi * 400 * i / sample_rate))
                        struct.pack_into('<h', frames, i * 2, v)
                    wf.writeframes(bytes(frames))
                with open(path, 'wb') as f: f.write(buf.getvalue())
            except: pass
        try:
            if os.path.exists(path): self.sound_move = SoundLoader.load(path)
            self.bg_music = SoundLoader.load('music.ogg')
            if self.bg_music:
                self.bg_music.loop = True
                self.bg_music.volume = self.music_volume
        except: pass

    def play_music(self):
        if self.bg_music and self.bg_music.state != 'play': self.bg_music.play()
    def stop_music(self):
        if self.bg_music and self.bg_music.state == 'play': self.bg_music.stop()
    def play_sound(self):
        if self.sound_move: self.sound_move.play()

    def save_session(self):
        with open(os.path.join(self.user_data_dir, 'session.json'), 'w') as f: json.dump({'login': self.current_user}, f)
    def load_session(self):
        path = os.path.join(self.user_data_dir, 'session.json')
        if os.path.exists(path):
            try:
                with open(path, 'r') as f: self.current_user = json.load(f).get('login')
                if self.current_user: return True
            except: pass
        return False
    def logout_session(self):
        path = os.path.join(self.user_data_dir, 'session.json')
        if os.path.exists(path):
            try: os.remove(path) 
            except: pass

    def save_user_data(self):
        if self.current_user and not self.is_offline:
            path = os.path.join(self.user_data_dir, 'users.json')
            db = {}
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f: db = json.load(f)
                except: pass
            db[self.current_user] = db.get(self.current_user, {})
            db[self.current_user]['elo'] = self.player_elo
            with open(path, 'w', encoding='utf-8') as f: json.dump(db, f)

    def save_active_game(self, active):
        try:
            with open(os.path.join(self.user_data_dir, 'active_game.json'), 'w') as f:
                json.dump({'active': active, 'is_ranked': self.is_ranked}, f)
        except: pass

    def calculate_loss_penalty(self):
        base = {1: 12, 2: 25, 3: 37}.get(self.bot_diff, 12)
        elo = self.player_elo
        if elo <= 400: return max(5, base - 5)
        elif elo <= 500: return base
        elif elo >= 600: return base + ((elo - 600) // 100 + 1) * 5
        return base

if __name__ == '__main__':
    ChessApp().run()
