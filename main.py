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

# Импорты Kivy для интерфейса
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
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.animation import Animation
from kivy.network.urlrequest import UrlRequest
from kivy.graphics import Color, RoundedRectangle, Ellipse, Rectangle

# Регистрация кастомного шрифта для фигур
LabelBase.register(name='ChessFont', fn_regular='DejaVuSans.ttf')

# АДРЕС СЕРВЕРА
SERVER_URL = "http://node.waifly.com:27402"
# ССЫЛКА НА САЙТ ДЛЯ СКАЧИВАНИЯ
SITE_URL = "https://barabulka8xx-del.github.io/chess-site/" 

# ТЕКУЩАЯ ВЕРСИЯ ИГРЫ
GAME_VERSION = "1.0"

# ================== КАСТОМНЫЕ ЭЛЕМЕНТЫ UI ==================

class RoundedButton(Button):
    """Кнопка с закругленными углами и правильным цветом фона."""
    def __init__(self, **kwargs):
        bg_col = kwargs.pop('background_color', (0.4, 0.4, 0.4, 1))
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        with self.canvas.before:
            self.bg_color = Color(rgba=bg_col)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self.update_rect, size=self.update_rect)
        
    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class SquareButton(Button):
    """Кнопка для клетки шахматной доски."""
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

def inb(r, c): 
    return 0 <= r < 8 and 0 <= c < 8

def start_state():
    return {
        'board': [
            ['r','n','b','q','k','b','n','r'], ['p']*8,
            ['.']*8, ['.']*8, ['.']*8, ['.']*8,
            ['P']*8, ['R','N','B','Q','K','B','N','R'],
        ],
        'turn': 'w', 'castle_wk': True, 'castle_wq': True,
        'castle_bk': True, 'castle_bq': True, 'ep': None, 'halfmove': 0,
    }

def copy_state(s):
    return {
        'board': [row[:] for row in s['board']], 'turn': s['turn'],
        'castle_wk': s['castle_wk'], 'castle_wq': s['castle_wq'],
        'castle_bk': s['castle_bk'], 'castle_bq': s['castle_bq'],
        'ep': s['ep'], 'halfmove': s['halfmove'],
    }

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
            if t == '.':
                moves.append((r,c,nr,nc,None,None))
            else:
                if (turn=='w' and t.islower()) or (turn=='b' and t.isupper()):
                    moves.append((r,c,nr,nc,None,None))
                break
            nr += dr; nc += dc

def gen_pawn(b, r, c, turn, moves, ep):
    if turn=='w': fwd, start, promo = -1, 6, 0
    else:         fwd, start, promo =  1, 1, 7
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
            else:
                moves.append((r,c,nr,nc,None,None))
        elif ep and (nr,nc) == ep:
            moves.append((r,c,nr,nc,None,'ep'))

def gen_pseudo(s):
    b = s['board']; turn = s['turn']; ep = s['ep']
    moves = []
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
                        if (turn=='w' and (t=='.' or t.islower())) or (turn=='b' and (t=='.' or t.isupper())):
                            moves.append((r,c,nr,nc,None,None))
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
                            if (turn=='w' and (t=='.' or t.islower())) or (turn=='b' and (t=='.' or t.isupper())):
                                moves.append((r,c,nr,nc,None,None))
                if turn=='w' and (r,c)==(7,4):
                    if s['castle_wk'] and b[7][5]=='.' and b[7][6]=='.':
                        if not is_attacked(b,7,4,False) and not is_attacked(b,7,5,False) and not is_attacked(b,7,6,False):
                            moves.append((7,4,7,6,None,'O-O'))
                    if s['castle_wq'] and b[7][1]=='.' and b[7][2]=='.' and b[7][3]=='.':
                        if not is_attacked(b,7,4,False) and not is_attacked(b,7,3,False) and not is_attacked(b,7,2,False):
                            moves.append((7,4,7,2,None,'O-O-O'))
                if turn=='b' and (r,c)==(0,4):
                    if s['castle_bk'] and b[0][5]=='.' and b[0][6]=='.':
                        if not is_attacked(b,0,4,True) and not is_attacked(b,0,5,True) and not is_attacked(b,0,6,True):
                            moves.append((0,4,0,6,None,'O-O'))
                    if s['castle_bq'] and b[0][1]=='.' and b[0][2]=='.' and b[0][3]=='.':
                        if not is_attacked(b,0,4,True) and not is_attacked(b,0,3,True) and not is_attacked(b,0,2,True):
                            moves.append((0,4,0,2,None,'O-O-O'))
    return moves

def apply_move(s, m):
    ns = copy_state(s)
    b = ns['board']
    fr, fc, tr, tc, promo, sp = m
    piece = b[fr][fc]
    color = 'w' if piece.isupper() else 'b'
    captured = b[tr][tc]
    
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
    if piece.upper()=='P' and abs(tr-fr)==2:
        ns['ep'] = ((fr+tr)//2, fc)
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
    turn = s['turn']
    return [m for m in gen_pseudo(s) if not in_check(apply_move(s, m), turn)]

def insufficient_material(b):
    pieces = []
    bishop_colors = []
    for r in range(8):
        for c in range(8):
            p = b[r][c]
            if p != '.' and p.upper() != 'K': 
                pieces.append(p.lower())
                if p.lower() == 'b': 
                    bishop_colors.append((r + c) % 2)
    if len(pieces) == 0:
        return True
    if len(pieces) == 1 and pieces[0] in ['b', 'n']:
        return True
    if len(pieces) > 1 and all(p == 'b' for p in pieces):
        if len(set(bishop_colors)) == 1:
            return True
    return False

def game_status(s):
    if not legal_moves(s):
        return 'checkmate' if in_check(s, s['turn']) else 'stalemate'
    if s['halfmove'] >= 100: 
        return 'draw50'
    if insufficient_material(s['board']):
        return 'draw_material'
    return None

# ================== БОТ (МИНИМАКС) ==================

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
    if not moves:
        if in_check(s, s['turn']): return -99999 if maximizing else 99999
        return 0
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
        val = minimax(apply_move(s, m), 2, -float('inf'), float('inf'), True)
        val += random.randint(-10, 10)
        if val < best_val: 
            best_val = val
            best_move = m
    return best_move
    # ================== ЭКРАНЫ ПРИЛОЖЕНИЯ ==================

class LoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        main_layout = FloatLayout()
        self.bg_image = Image(source='icon.png', allow_stretch=True, keep_ratio=False, size_hint=(1, 1), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        main_layout.add_widget(self.bg_image)
        ui_layout = BoxLayout(orientation='vertical', size_hint=(1, 1), padding=dp(20))
        ui_layout.add_widget(Label(size_hint_y=0.85)) 
        self.status = Label(text="Загрузка...", font_size=dp(24), color=(1,1,1,1), size_hint_y=0.15)
        ui_layout.add_widget(self.status)
        main_layout.add_widget(ui_layout)
        self.add_widget(main_layout)
        self.anim = Animation(opacity=0.6, duration=1.0) + Animation(opacity=1.0, duration=1.0)
        self.anim.repeat = True
        self.anim.start(self.bg_image)

    def go_next(self, dt):
        self.anim.stop(self.bg_image)
        app = App.get_running_app()
        if app.load_session(): 
            self.manager.current = 'main_menu' 
        else: 
            self.manager.current = 'login'     

class BackgroundScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_layout = FloatLayout()
        self.bg = Image(source='menu_bg.png', allow_stretch=True, keep_ratio=False, size_hint=(1, 1), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.main_layout.add_widget(self.bg)
        self.add_widget(self.main_layout)

class ChessBoard(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 8
        self.rows = 8
        self.squares = {}
        self.build_board()

    def build_board(self):
        for r in range(8):
            for c in range(8):
                color = (0.93, 0.84, 0.72, 1) if (r+c)%2==0 else (0.71, 0.53, 0.39, 1)
                btn = SquareButton(r, c, text="", background_color=color)
                btn.bind(on_release=self.on_square_click)
                self.squares[(r,c)] = btn
                self.add_widget(btn)

    def on_square_click(self, instance):
        app = App.get_running_app()
        app.game_screen.handle_square_click(instance.r, instance.c)

    def update_board(self, board, selected, legal_targets, last_move):
        for (r, c), btn in self.squares.items():
            base_color = (0.93, 0.84, 0.72, 1) if (r+c)%2==0 else (0.71, 0.53, 0.39, 1)
            btn.set_bg_color(base_color)
            btn.text = ""
            btn.show_dot(False)
            
        piece_map = {'K':'♚','Q':'♛','R':'♜','B':'♝','N':'♞','P':'♟', 'k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}
        
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
            tr, tc = m[2], m[3]
            self.squares[(tr,tc)].show_dot(True)

class LoginScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = 'login' 
        layout = BoxLayout(orientation='vertical', padding=dp(40), spacing=dp(10), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.title_label = Label(text="Вход в аккаунт", font_size=dp(32), bold=True, size_hint_y=0.15)
        layout.add_widget(self.title_label)
        self.login_input = TextInput(hint_text="Логин (на англ.)", multiline=False, size_hint_y=0.1, font_size=dp(20))
        layout.add_widget(self.login_input)
        self.pass_input = TextInput(hint_text="Пароль", password=True, multiline=False, size_hint_y=0.1, font_size=dp(20))
        layout.add_widget(self.pass_input)
        self.status_label = Label(text="", color=(1, 0.3, 0.3, 1), size_hint_y=0.1)
        layout.add_widget(self.status_label)
        self.submit_btn = RoundedButton(text="Войти", size_hint_y=0.12, font_size=dp(20), background_color=(0.2, 0.6, 0.2, 1))
        self.submit_btn.bind(on_release=self.handle_submit)
        layout.add_widget(self.submit_btn)
        self.toggle_btn = RoundedButton(text="Нет аккаунта? Регистрация", size_hint_y=0.1, font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        self.toggle_btn.bind(on_release=self.toggle_mode)
        layout.add_widget(self.toggle_btn)
        self.offline_btn = RoundedButton(text="Играть без интернета (Офлайн)", size_hint_y=0.1, font_size=dp(16), background_color=(0.5, 0.3, 0.1, 1))
        self.offline_btn.bind(on_release=self.play_offline)
        layout.add_widget(self.offline_btn)
        info_label = Label(text="(i) для регистрации потребуется интернет", font_size=dp(11), color=(0.7, 0.7, 0.7, 1), size_hint_y=0.05)
        layout.add_widget(info_label)
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        App.get_running_app().play_music()

    def play_offline(self, instance):
        app = App.get_running_app()
        app.is_offline = True
        app.current_user = "Гость"
        app.player_elo = 0
        app.logout_session() 
        self.manager.current = 'main_menu'

    def toggle_mode(self, instance):
        if self.mode == 'login':
            self.mode = 'register'
            self.title_label.text = "Регистрация"
            self.submit_btn.text = "Зарегистрироваться"
            self.toggle_btn.text = "Уже есть аккаунт? Войти"
        else:
            self.mode = 'login'
            self.title_label.text = "Вход в аккаунт"
            self.submit_btn.text = "Войти"
            self.toggle_btn.text = "Нет аккаунта? Регистрация"
        self.status_label.text = ""
        self.login_input.text = ""
        self.pass_input.text = ""

    def handle_submit(self, instance):
        login = self.login_input.text.strip()
        password = self.pass_input.text.strip()
        if not login or not password:
            self.status_label.text = "Заполните все поля!"
            return
        if not re.match(r'^[A-Za-z0-9_$#.]{3,20}$', login):
            self.status_label.text = "Недопустимые символы в логине!"
            return
        self.status_label.text = "Подключение к серверу..."
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
                self.status_label.text = "Неверный пароль" if req.resp_status == 401 else "Ошибка сервера"
            def on_network_fail(req, error):
                self.submit_btn.disabled = False
                self.status_label.color = (1, 0.3, 0.3, 1)
                self.status_label.text = "Нет соединения с сервером"
            UrlRequest(f"{SERVER_URL}/login", req_body=req_body, req_headers=req_headers, on_success=on_success, on_error=on_error, on_failure=on_network_fail, timeout=10)
        else:
            def on_success(req, result):
                self.submit_btn.disabled = False
                self.status_label.color = (0, 1, 0, 1)
                self.status_label.text = "Успешно! Теперь войдите."
                self.toggle_mode(None) 
            def on_error(req, error):
                self.submit_btn.disabled = False
                self.status_label.color = (1, 0.3, 0.3, 1)
                self.status_label.text = "Этот логин уже занят!" if req.resp_status == 400 else "Ошибка сервера"
            def on_network_fail(req, error):
                self.submit_btn.disabled = False
                self.status_label.color = (1, 0.3, 0.3, 1)
                self.status_label.text = "Нет соединения с сервером"
            UrlRequest(f"{SERVER_URL}/register", req_body=req_body, req_headers=req_headers, on_success=on_success, on_error=on_error, on_failure=on_network_fail, timeout=10)

class MainMenuScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ui_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(8), size_hint=(0.8, 0.95), pos_hint={'center_x': 0.5, 'center_y': 0.45})
        self.user_label = Label(text="", font_size=dp(18), color=(1, 1, 1, 1), size_hint_y=0.08)
        ui_layout.add_widget(self.user_label)
        ui_layout.add_widget(Label(text="Шахматы", font_size=dp(36), bold=True, size_hint_y=0.12))
        self.elo_label = Label(text="", font_size=dp(22), color=(1, 0.8, 0.2, 1), size_hint_y=0.08)
        ui_layout.add_widget(self.elo_label)
        btn_2p = RoundedButton(text="2 Игрока", font_size=dp(20), size_hint_y=0.11, background_color=(0.2, 0.6, 0.2, 1))
        btn_2p.bind(on_release=lambda x: setattr(self.manager, 'current', 'two_players_menu'))
        ui_layout.add_widget(btn_2p)
        btn_bot = RoundedButton(text="Игра с Ботом", font_size=dp(20), size_hint_y=0.11, background_color=(0.8, 0.5, 0.2, 1))
        btn_bot.bind(on_release=lambda x: self.start_bot_menu())
        ui_layout.add_widget(btn_bot)
        btn_ranked = RoundedButton(text="Ранговый матч", font_size=dp(20), size_hint_y=0.11, background_color=(0.2, 0.5, 0.8, 1))
        btn_ranked.bind(on_release=lambda x: self.start_ranked())
        ui_layout.add_widget(btn_ranked)
        self.admin_btn = RoundedButton(text="Отправить уведомление", font_size=dp(14), size_hint_y=0.08, background_color=(0.8, 0.2, 0.8, 1))
        self.admin_btn.bind(on_release=self.show_admin_panel)
        ui_layout.add_widget(self.admin_btn)
        btn_logout = RoundedButton(text="Выйти", font_size=dp(14), size_hint_y=0.08, background_color=(0.5, 0.2, 0.2, 1))
        btn_logout.bind(on_release=self.logout)
        ui_layout.add_widget(btn_logout)
        ui_layout.add_widget(Label(size_hint_y=0.05))
        ui_layout.add_widget(Label(text=f"v{GAME_VERSION}", font_size=dp(10), color=(0.5, 0.5, 0.5, 1), size_hint_y=0.05))
        ui_layout.add_widget(Label(text="Сделано Kirillom Der**", font_size=dp(12), color=(0.7, 0.7, 0.7, 1), size_hint_y=0.05))
        
        self.main_layout.add_widget(ui_layout)

        # КРУГЛАЯ КНОПКА (i) В ПРАВОМ НИЖНЕМ УГЛУ
        self.info_btn = RoundedButton(
            text="(i)", font_size=dp(20), bold=True,
            size_hint=(None, None), size=(dp(50), dp(50)),
            pos_hint={'right': 0.95, 'y': 0.05},
            background_color=(0.2, 0.5, 0.8, 1)
        )
        self.info_btn.rect.radius = [dp(25)] # Делаем её круглой
        self.info_btn.bind(on_release=self.show_changelog)
        self.main_layout.add_widget(self.info_btn)

    def show_changelog(self, instance):
        """Окно с историей обновлений."""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        scroll = ScrollView()
        layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(15))
        layout.bind(minimum_height=layout.setter('height'))
        
        title = Label(text="[b][color=f1c40f]История обновлений[/color][/b]", markup=True, font_size=dp(22), size_hint_y=None, height=dp(50))
        layout.add_widget(title)
        
        log_text = (
            "[b]Обновление 1[/b]\n"
            "• Самый первый релиз игры.\n"
            "• Игра с ботом, онлайн по коду, ранговый матч.\n"
            "• Система рейтинга ЭЛО.\n\n"
            "[b]Обновление 2[/b]\n"
            "• Исправлены вылеты при запуске (фикс шрифтов и звука).\n"
            "• Исправлена проблема с пропаданием ЭЛО после игры с ботом.\n"
            "• Добавлена проверка версии (блокировка старых APK в ранге).\n"
            "• Добавлена ничья при нехватке фигур (Insufficient material).\n"
            "• Исправлен выход текста за края экрана в окнах.\n"
            "• Добавлена кнопка (i) с информацией.\n"
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

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        self.user_label.text = f"Вы вошли как: {app.current_user}"
        if app.current_user == "DEV$DEV":
            self.admin_btn.opacity = 1
            self.admin_btn.disabled = False
        else:
            self.admin_btn.opacity = 0
            self.admin_btn.disabled = True

        if app.is_offline:
            self.elo_label.text = "ЭЛО: Недоступно (Офлайн)"
            self.elo_label.color = (0.5, 0.5, 0.5, 1)
        else:
            def sync_success(req, result):
                app.player_elo = result.get('elo', app.player_elo)
                app.save_user_data()
                self.elo_label.text = f"Ваш ЭЛО: {app.player_elo}"
                self.elo_label.color = (1, 0.8, 0.2, 1)
            def sync_fail(req, error):
                self.elo_label.text = f"ЭЛО: {app.player_elo} (Нет сети)"
                self.elo_label.color = (0.8, 0.5, 0.2, 1)
            if app.current_user:
                UrlRequest(f"{SERVER_URL}/sync_elo/{app.current_user}", on_success=sync_success, on_error=sync_fail, on_failure=sync_fail)
            self.check_developer_notification()
        app.play_music()

    def show_admin_panel(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
        input_text = TextInput(hint_text="Текст уведомления для игроков...", multiline=False, size_hint_y=None, height=dp(50))
        content.add_widget(input_text)
        btn_layout = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(50))
        popup = Popup(title="Рассылка", content=content, size_hint=(0.8, 0.4))
        
        def send_notification(req_inst):
            msg = input_text.text.strip()
            if not msg: return
            req_body = json.dumps({"login": "DEV$DEV", "password": "AKS.2GmOZx#Z", "message": msg})
            def on_success(req, res):
                popup.dismiss()
                App.get_running_app().last_seen_notification = None
                Popup(title="Успех", content=Label(text="Уведомление разослано!"), size_hint=(0.8, 0.3)).open()
            UrlRequest(f"{SERVER_URL}/admin/send_update", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=on_success)

        def clear_notification(req_inst):
            req_body = json.dumps({"login": "DEV$DEV", "password": "AKS.2GmOZx#Z", "message": ""})
            def on_success(req, res):
                popup.dismiss()
                Popup(title="Успех", content=Label(text="Уведомления отключены."), size_hint=(0.8, 0.3)).open()
            UrlRequest(f"{SERVER_URL}/admin/clear_notification", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=on_success)
        
        btn_send = RoundedButton(text="Отправить", background_color=(0.2, 0.6, 0.2, 1))
        btn_send.bind(on_release=send_notification)
        btn_layout.add_widget(btn_send)
        btn_clear = RoundedButton(text="Отключить", background_color=(0.8, 0.2, 0.2, 1))
        btn_clear.bind(on_release=clear_notification)
        btn_layout.add_widget(btn_clear)
        content.add_widget(btn_layout)
        popup.open()

    def check_developer_notification(self):
        def on_success(req, result):
            app = App.get_running_app()
            if result and result.get('active'):
                msg = result.get('message', '')
                if msg and msg != app.last_seen_notification:
                    app.last_seen_notification = msg
                    content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
                    
                    # ФИКС ПЕРЕНОСА ТЕКСТА
                    notif_lbl = Label(text=msg, halign="center", font_size=dp(18))
                    notif_lbl.bind(size=lambda instance, value: setattr(instance, 'text_size', (value[0], None)))
                    content.add_widget(notif_lbl)
                    
                    btn_layout = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(50))
                    btn_old = RoundedButton(text="Играть на старой", background_color=(0.3, 0.3, 0.3, 1))
                    btn_old.bind(on_release=lambda x: popup.dismiss())
                    btn_layout.add_widget(btn_old)
                    btn_new = RoundedButton(text="Скачать новую", background_color=(0.2, 0.6, 0.2, 1))
                    def open_site(instance):
                        popup.dismiss()
                        webbrowser.open(SITE_URL) 
                    btn_new.bind(on_release=open_site)
                    btn_layout.add_widget(btn_new)
                    content.add_widget(btn_layout)
                    popup = Popup(title="Обновление!", content=content, size_hint=(0.85, 0.4), auto_dismiss=False)
                    popup.open()
        UrlRequest(f"{SERVER_URL}/get_notification", on_success=on_success, on_failure=lambda req, err: None)

    def logout(self, instance):
        app = App.get_running_app()
        app.current_user = None
        app.player_elo = 300
        app.is_offline = False
        app.logout_session()
        self.manager.current = 'login'

    def start_bot_menu(self):
        app = App.get_running_app()
        app.is_ranked = False
        app.is_online = False
        self.manager.current = 'bot_menu'

    def start_ranked(self):
        app = App.get_running_app()
        if app.is_offline:
            Popup(title="Офлайн", content=Label(text="Ранговые матчи недоступны\nбез интернета."), size_hint=(0.8, 0.3)).open()
            return
        self.manager.current = 'ranked_menu'

class TwoPlayersMenuScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        layout.add_widget(Label(text="Игра на двоих", font_size=dp(30), bold=True, size_hint_y=0.2))
        btn_local = RoundedButton(text="На одном устройстве", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.6, 0.2, 1))
        btn_local.bind(on_release=self.start_local)
        layout.add_widget(btn_local)
        btn_online = RoundedButton(text="Онлайн по коду", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.5, 0.8, 1))
        btn_online.bind(on_release=self.show_room_menu)
        layout.add_widget(btn_online)
        btn_back = RoundedButton(text="Назад", font_size=dp(20), size_hint_y=0.15, background_color=(0.5, 0.2, 0.2, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'main_menu'))
        layout.add_widget(btn_back)
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        App.get_running_app().play_music()

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
            Popup(title="Офлайн", content=Label(text="Онлайн по коду недоступен\nбез интернета."), size_hint=(0.8, 0.3)).open()
            return

        def ping_fail(req, err):
            Popup(title="Нет сети", content=Label(text="Сервер недоступен."), size_hint=(0.8, 0.3)).open()

        def ping_success(req, result):
            content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
            btn_create = RoundedButton(text="Создать комнату", size_hint_y=None, height=dp(50), background_color=(0.2, 0.7, 0.2, 1))
            btn_join = RoundedButton(text="Войти по коду", size_hint_y=None, height=dp(50), background_color=(0.2, 0.5, 0.8, 1))
            code_input = TextInput(hint_text="Код комнаты", multiline=False, size_hint_y=None, height=dp(50))
            content.add_widget(btn_create)
            content.add_widget(code_input)
            content.add_widget(btn_join)
            self.room_popup = Popup(title="Онлайн по коду", content=content, size_hint=(0.8, 0.5))
            
            def create_req(req, result):
                self.room_popup.dismiss()
                Popup(title="Комната создана", content=Label(text=f"Код: {result['room_id']}\nЖдем соперника..."), size_hint=(0.8, 0.4)).open()
                self.poll_join(result['room_id'])

            def join_req(req, result):
                self.room_popup.dismiss()
                app.is_online = True
                app.is_ranked = False
                app.online_room_id = code_input.text.upper()
                app.online_color = 'black'
                app.online_opponent = result.get('opponent', 'Соперник')
                app.game_screen.new_game()
                self.manager.current = 'game'

            def create_fail(req, err):
                Popup(title="Ошибка", content=Label(text="Не удалось создать комнату"), size_hint=(0.8, 0.3)).open()

            def join_fail(req, err):
                Popup(title="Ошибка", content=Label(text="Комната не найдена\nили нет сети"), size_hint=(0.8, 0.3)).open()

            btn_create.bind(on_release=lambda x: UrlRequest(f"{SERVER_URL}/create_room", req_body=json.dumps({"login": app.current_user}), req_headers={'Content-Type': 'application/json'}, on_success=create_req, on_error=create_fail, on_failure=create_fail))
            btn_join.bind(on_release=lambda x: UrlRequest(f"{SERVER_URL}/join_room", req_body=json.dumps({"login": app.current_user, "room_code": code_input.text.upper()}), req_headers={'Content-Type': 'application/json'}, on_success=join_req, on_error=join_fail, on_failure=join_fail))
            self.room_popup.open()

        UrlRequest(f"{SERVER_URL}/ping", on_success=ping_success, on_error=ping_fail, on_failure=ping_fail, timeout=5)

    def poll_join(self, room_id):
        app = App.get_running_app()
        def check(req, result):
            if result.get('board_data') is not None:
                app.is_online = True
                app.is_ranked = False
                app.online_room_id = room_id
                app.online_color = 'white'
                app.game_screen.new_game()
                self.manager.current = 'game'
            else: 
                Clock.schedule_once(lambda dt: self.poll_join(room_id), 2)
        def check_fail(req, err):
            Clock.schedule_once(lambda dt: self.poll_join(room_id), 3)
        UrlRequest(f"{SERVER_URL}/get_move/{room_id}", on_success=check, on_failure=check_fail)

class RankedMenuScreen(BackgroundScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_searching = False
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        layout.add_widget(Label(text="Ранговый матч", font_size=dp(30), bold=True, size_hint_y=0.2))
        btn_find = RoundedButton(text="Найти соперника (Онлайн)", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.6, 0.8, 1))
        btn_find.bind(on_release=self.find_online_match)
        layout.add_widget(btn_find)
        btn_bot = RoundedButton(text="С Ботом", font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.6, 0.2, 1))
        btn_bot.bind(on_release=self.start_ranked_bot)
        layout.add_widget(btn_bot)
        btn_back = RoundedButton(text="Назад", font_size=dp(20), size_hint_y=0.15, background_color=(0.5, 0.2, 0.2, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'main_menu'))
        layout.add_widget(btn_back)
        self.server_status_label = Label(text="проверка сервера...", font_size=dp(12), color=(1, 1, 0, 1), size_hint_y=0.1)
        layout.add_widget(self.server_status_label)
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        App.get_running_app().play_music()
        self.check_server_status()

    def check_server_status(self):
        def on_success(req, result):
            self.server_status_label.text = "сервер онлайн"
            self.server_status_label.color = (0, 1, 0, 1)
        def on_fail(req, error):
            self.server_status_label.text = "сервер офлайн"
            self.server_status_label.color = (1, 0, 0, 1)
        UrlRequest(f"{SERVER_URL}/ping", on_success=on_success, on_error=on_fail, on_failure=on_fail, timeout=5)

    def find_online_match(self, instance):
        app = App.get_running_app()
        def ping_fail(req, err):
            Popup(title="Нет сети", content=Label(text="Проверьте интернет."), size_hint=(0.8, 0.3)).open()

        def ping_success(req, result):
            self.is_searching = True
            content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
            content.add_widget(Label(text="Ищем соперника...\nПодождите."))
            btn_cancel = RoundedButton(text="Отменить поиск", size_hint_y=None, height=dp(50), background_color=(0.8, 0.2, 0.2, 1))
            btn_cancel.bind(on_release=self.cancel_search)
            content.add_widget(btn_cancel)
            self.waiting_popup = Popup(title="Поиск", content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
            self.waiting_popup.open()
            
            def show_update_popup():
                content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
                
                # ФИКС ПЕРЕНОСА ТЕКСТА
                lbl = Label(text="Вышло обновление игры!\nПожалуйста, скачайте новую версию, чтобы играть в ранговый матч.", halign="center", font_size=dp(16))
                lbl.bind(size=lambda instance, value: setattr(instance, 'text_size', (value[0], None)))
                content.add_widget(lbl)
                
                btn = RoundedButton(text="Скачать обновление", size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.2, 1))
                def open_site(instance):
                    self.update_popup.dismiss()
                    webbrowser.open(SITE_URL) 
                btn.bind(on_release=open_site)
                content.add_widget(btn)
                self.update_popup = Popup(title="Обновление", content=content, size_hint=(0.85, 0.4), auto_dismiss=False)
                self.update_popup.open()

            def on_success(req, result):
                if not self.is_searching: return
                if result.get('status') == 'waiting': 
                    Clock.schedule_once(lambda dt: self.check_match_status(app), 2)
                elif result.get('status') == 'matched':
                    self.is_searching = False
                    self.start_online_game(result['room_id'], result['color'], result['opponent'], result.get('opponent_elo', 300))
                    
            def on_error(req, error):
                self.waiting_popup.dismiss()
                self.is_searching = False
                if getattr(req, 'resp_status', None) == 403:
                    show_update_popup()
                else: 
                    Popup(title="Ошибка", content=Label(text="Сервер недоступен"), size_hint=(0.8, 0.3)).open()

            def on_network_fail(req, error):
                self.waiting_popup.dismiss()
                self.is_searching = False
                if getattr(req, 'resp_status', None) == 403:
                    show_update_popup()
                else:
                    Popup(title="Нет сети", content=Label(text="Сервер не отвечает"), size_hint=(0.8, 0.3)).open()

            req_body = json.dumps({"login": app.current_user, "elo": app.player_elo, "version": GAME_VERSION})
            UrlRequest(f"{SERVER_URL}/find_match", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=on_success, on_error=on_error, on_failure=on_network_fail)
            
        UrlRequest(f"{SERVER_URL}/ping", on_success=ping_success, on_error=ping_fail, on_failure=ping_fail, timeout=5)

    def cancel_search(self, instance):
        self.is_searching = False
        self.waiting_popup.dismiss()
        app = App.get_running_app()
        UrlRequest(f"{SERVER_URL}/cancel_search", req_body=json.dumps({"login": app.current_user}), req_headers={'Content-Type': 'application/json'})

    def check_match_status(self, app):
        if not self.is_searching: return
        if not getattr(self.waiting_popup, '_window', None): return
        def on_success(req, result):
            if not self.is_searching: return
            if result.get('status') == 'matched':
                self.is_searching = False
                self.start_online_game(result['room_id'], result['color'], result['opponent'], result.get('opponent_elo', 300))
            elif result.get('status') == 'waiting':
                req_body = json.dumps({"login": app.current_user, "elo": app.player_elo, "version": GAME_VERSION})
                UrlRequest(f"{SERVER_URL}/find_match", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=lambda r, res: Clock.schedule_once(lambda dt: self.check_match_status(app), 2), on_failure=lambda r, e: Clock.schedule_once(lambda dt: self.check_match_status(app), 3))
        def check_fail(req, err):
            if self.is_searching:
                Clock.schedule_once(lambda dt: self.check_match_status(app), 3)
        UrlRequest(f"{SERVER_URL}/check_match/{app.current_user}", on_success=on_success, on_failure=check_fail)

    def start_online_game(self, room_id, color, opponent, opp_elo):
        self.waiting_popup.dismiss()
        app = App.get_running_app()
        app.is_online = True
        app.is_ranked = True
        app.game_mode = 'bot'
        app.online_room_id = room_id
        app.online_color = color
        app.online_opponent = opponent
        app.online_opponent_elo = opp_elo
        app.game_screen.new_game()
        self.manager.current = 'game'
        popup = Popup(title="Игра началась", content=Label(text=f"Соперник: {opponent} ({opp_elo} ЭЛО)\nВаш цвет: {'Белые' if color == 'white' else 'Черные'}"), size_hint=(0.8, 0.3))
        popup.open()

    def start_ranked_bot(self, instance):
        app = App.get_running_app()
        elo = app.player_elo
        if elo <= 450: diff = 1
        elif elo <= 1000: diff = 2
        else: diff = 3
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
        layout.add_widget(Label(text="Сложность", font_size=dp(30), size_hint_y=0.3))
        for diff, text in [(1, "Легкий"), (2, "Средний"), (3, "Сложный")]:
            btn = RoundedButton(text=text, font_size=dp(20), size_hint_y=0.15, background_color=(0.2, 0.5, 0.8, 1))
            btn.bind(on_release=lambda x, d=diff: self.start_bot(d))
            layout.add_widget(btn)
        btn_back = RoundedButton(text="Назад", font_size=dp(20), size_hint_y=0.15, background_color=(0.5, 0.2, 0.2, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'main_menu'))
        layout.add_widget(btn_back)
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        App.get_running_app().play_music()

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
        self.exit_popup = None
        self.time_left = 45
        self.timer_event = None
        self.poll_event = None
        
        main_layout = BoxLayout(orientation='vertical')
        top_bar = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(5), padding=dp(5))
        btn_menu = RoundedButton(text="Меню", font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        btn_menu.bind(on_release=self.go_to_menu)
        top_bar.add_widget(btn_menu)
        self.status_label = Label(text="Ход белых", font_size=dp(16), bold=True)
        top_bar.add_widget(self.status_label)
        self.timer_label = Label(text="", font_size=dp(18), bold=True, color=(1, 0.5, 0.5, 1))
        top_bar.add_widget(self.timer_label)
        self.btn_undo = RoundedButton(text="Отмена", font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        self.btn_undo.bind(on_release=self.undo_move)
        top_bar.add_widget(self.btn_undo)
        main_layout.add_widget(top_bar)
        
        self.match_info_layout = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(10))
        self.opp_label = Label(text="", font_size=dp(14), halign="left", valign="middle")
        self.opp_label.bind(size=self.opp_label.setter('text_size'))
        self.match_info_layout.add_widget(self.opp_label)
        self.my_label = Label(text="", font_size=dp(14), halign="right", valign="middle")
        self.my_label.bind(size=self.my_label.setter('text_size'))
        self.match_info_layout.add_widget(self.my_label)
        main_layout.add_widget(self.match_info_layout)
        
        board_container = FloatLayout()
        self.board_ui = ChessBoard(size_hint=(0.95, None), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.board_ui.bind(width=lambda instance, value: setattr(instance, 'height', value))
        board_container.add_widget(self.board_ui)
        main_layout.add_widget(board_container)
        self.add_widget(main_layout)

    def on_pre_enter(self, *args):
        App.get_running_app().stop_music()

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
        
        if app.is_online and app.is_ranked:
            opp_name = getattr(app, 'online_opponent', 'Соперник')
            opp_elo = getattr(app, 'online_opponent_elo', '?')
            my_elo = app.player_elo
            self.opp_label.text = f"Соперник: {opp_name}\n(ЭЛО: {opp_elo})"
            self.opp_label.color = (1, 0.4, 0.4, 1)
            self.my_label.text = f"Вы: {app.current_user}\n(ЭЛО: {my_elo})"
            self.my_label.color = (0.4, 1, 0.4, 1)
            self.match_info_layout.opacity = 1
        else:
            self.match_info_layout.opacity = 0 
            
        if app.is_ranked or app.is_online:
            self.btn_undo.text = "Без отмены"
            self.btn_undo.disabled = True
            self.btn_undo.background_color = (0.2, 0.2, 0.2, 1)
            app.save_active_game(True) 
            self.reset_timer()
        else:
            self.btn_undo.text = "Отмена"
            self.btn_undo.disabled = False
            self.btn_undo.background_color = (0.3, 0.3, 0.3, 1)
            app.save_active_game(False)
            self.stop_timer()
            self.timer_label.text = ""
        if app.is_online:
            self.start_polling() 
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
                if app.is_ranked:
                    self.reset_timer()
        def on_fail(req, error):
            if req.resp_status == 404:
                self.stop_polling()
                self.stop_timer()
                self.game_over_triggered = True
                def sync_success(r, res):
                    app.player_elo = res.get('elo', app.player_elo)
                    app.save_user_data()
                    self.show_end_popup("ПОБЕДА!", "Соперник покинул игру.\nВам засчитана победа!\n\nВаш ЭЛО: " + str(app.player_elo))
                def sync_err(r, e):
                    self.show_end_popup("ПОБЕДА!", "Соперник покинул игру.\nВам засчитана победа!\n\n(Не удалось синхронизировать ЭЛО)")
                UrlRequest(f"{SERVER_URL}/sync_elo/{app.current_user}", on_success=sync_success, on_failure=sync_err, on_error=sync_err)
        UrlRequest(f"{SERVER_URL}/get_move/{app.online_room_id}", on_success=on_success, on_error=on_fail, on_failure=lambda r, e: None)

    def start_timer(self):
        self.stop_timer()
        app = App.get_running_app()
        if not (app.is_ranked or app.is_online): return
        my_color = 'w' if not hasattr(app, 'online_color') else ('w' if app.online_color == 'white' else 'b')
        if self.state['turn'] != my_color: return
        self.timer_label.color = (1, 0.5, 0.5, 1)
        self.timer_label.text = f"Время: {self.time_left}с"
        self.timer_event = Clock.schedule_interval(self.tick_timer, 1)

    def stop_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def tick_timer(self, dt):
        if game_status(self.state) is not None:
            self.stop_timer()
            return
        self.time_left -= 1
        if self.time_left <= 5:
            self.timer_label.color = (1, 0, 0, 1)
            self.timer_label.text = f"Осталось: {self.time_left}с"
        else:
            self.timer_label.color = (1, 0.5, 0.5, 1)
            self.timer_label.text = f"Время: {self.time_left}с"
        if self.time_left <= 0:
            self.stop_timer()
            self.time_out_loss()

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
            if app.is_online and app.online_room_id:
                req_body = json.dumps({"room_id": app.online_room_id, "winner": app.online_opponent, "is_ranked": True})
                UrlRequest(f"{SERVER_URL}/finish_game", req_body=req_body, req_headers={'Content-Type': 'application/json'})
            else:
                req_body = json.dumps({"login": app.current_user, "elo_change": -penalty})
                UrlRequest(f"{SERVER_URL}/update_bot_elo", req_body=req_body, req_headers={'Content-Type': 'application/json'})
            msg = f"Время вышло!\nЗасчитано как поражение.\n\n-{penalty} ЭЛО\nВаш рейтинг: {app.player_elo}"
        else: 
            msg = "Время вышло!"
        self.show_end_popup("ПОРАЖЕНИЕ", msg)

    def update_ui(self):
        self.board_ui.update_board(self.state['board'], self.selected, self.legal_targets, self.last_move)
        self.status_label.text = self.get_status_text()
        st = game_status(self.state)
        if st == 'checkmate' or in_check(self.state, self.state['turn']):
            self.status_label.color = (1, 0.2, 0.2, 1)
        else: 
            self.status_label.color = (1, 1, 1, 1)
        self.check_game_over()

    def check_game_over(self):
        st = game_status(self.state)
        if st in ('stalemate', 'draw50', 'draw_material') and not self.game_over_triggered:
            self.game_over_triggered = True
            self.stop_timer()
            self.stop_polling()
            app = App.get_running_app()
            app.save_active_game(False)
            if st == 'stalemate':
                msg = "Пат! Ничья.\n\nЭЛО не изменилось."
            elif st == 'draw50':
                msg = "Ничья (правило 50 ходов).\n\nЭЛО не изменилось."
            else:
                msg = "Ничья (недостаточно фигур для мата).\n\nЭЛО не изменилось."
            self.show_end_popup("НИЧЬЯ", msg)
            return
            
        if st == 'checkmate' and not self.game_over_triggered:
            self.game_over_triggered = True
            self.stop_timer()
            self.stop_polling()
            app = App.get_running_app()
            app.save_active_game(False)
            if self.state['turn'] == 'b':
                title_text = "ПОБЕДА БЕЛЫХ!" if app.game_mode == '2p' else "ПОБЕДА!"
            else:
                title_text = "ПОБЕДА ЧЁРНЫХ!" if app.game_mode == '2p' else "ПОРАЖЕНИЕ"
                
            if app.is_online:
                winner = app.current_user if self.state['turn'] == 'b' else app.online_opponent
                req_body = json.dumps({"room_id": app.online_room_id, "winner": winner, "is_ranked": app.is_ranked})
                def send_result(req, res):
                    if res and 'players' in res:
                        if app.current_user == res['players'][0]: app.player_elo = res['new_elo_p1']
                        else: app.player_elo = res['new_elo_p2']
                        app.save_user_data()
                UrlRequest(f"{SERVER_URL}/finish_game", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=send_result)
                if app.is_ranked: msg = "Игра окончена!\n\nЭЛО обновлено (см. в меню)."
                else: msg = "Игра окончена.\n\nВ дружеском матче ЭЛО не начисляется."
            elif app.is_ranked:
                if self.state['turn'] == 'b':
                    base_points = {1: 12, 2: 25, 3: 37}.get(app.bot_diff, 12)
                    app.player_elo += base_points
                    app.save_user_data()
                    req_body = json.dumps({"login": app.current_user, "elo_change": base_points})
                    UrlRequest(f"{SERVER_URL}/update_bot_elo", req_body=req_body, req_headers={'Content-Type': 'application/json'})
                    msg = f"Вы поставили мат!\n\n+{base_points} ЭЛО\nВаш новый рейтинг: {app.player_elo}"
                else:
                    penalty = app.calculate_loss_penalty()
                    app.player_elo = max(0, app.player_elo - penalty)
                    app.save_user_data()
                    req_body = json.dumps({"login": app.current_user, "elo_change": -penalty})
                    UrlRequest(f"{SERVER_URL}/update_bot_elo", req_body=req_body, req_headers={'Content-Type': 'application/json'})
                    msg = f"Бот поставил вам мат.\n\n-{penalty} ЭЛО\nВаш рейтинг: {app.player_elo}"
            else:
                if app.game_mode == 'bot':
                    msg = "Вы поставили мат!\n\nВ обычной игре ЭЛО не начисляется." if self.state['turn'] == 'b' else "Бот поставил вам мат.\n\nВ обычной игре ЭЛО не начисляется."
                else:
                    msg = "Игра окончена матом.\n\nВ игре на двоих ЭЛО не начисляется."
            self.show_end_popup(title_text, msg)

    def show_end_popup(self, title, text):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text=text, halign="center", font_size=dp(18)))
        btn = RoundedButton(text="В меню", size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.2, 1))
        content.add_widget(btn)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
        def go_menu(instance):
            popup.dismiss()
            self.manager.current = 'main_menu'
        btn.bind(on_release=go_menu)
        popup.open()

    def get_status_text(self):
        if self.bot_thinking: return "Бот думает..."
        st = game_status(self.state)
        if st == 'checkmate': return "МАТ!"
        if st == 'stalemate': return "Ничья (пат)."
        if st == 'draw50': return "Ничья (50 ходов)."
        if st == 'draw_material': return "Ничья (мало фигур)." 
        if in_check(self.state, self.state['turn']):
            return "ШАХ! Ход белых" if self.state['turn'] == 'w' else "ШАХ! Ход чёрных"
        return "Ход белых" if self.state['turn'] == 'w' else "Ход чёрных"

    def go_to_menu(self, instance):
        app = App.get_running_app()
        if (app.is_ranked or app.is_online) and game_status(self.state) is None:
            self.show_exit_warning() 
        else:
            self.stop_timer()
            self.stop_polling()
            self.exit_to_menu()

    def show_exit_warning(self):
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
        app = App.get_running_app()
        penalty = app.calculate_loss_penalty() + 10
        content.add_widget(Label(text=f"Вы уверены, что хотите выйти?\nЭто засчитается как поражение (+10 к штрафу)!\nВы потеряете {penalty} ЭЛО!", halign="center", font_size=dp(16)))
        btn_layout = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(50))
        btn_yes = RoundedButton(text="Да, выйти", background_color=(0.8, 0.2, 0.2, 1))
        btn_yes.bind(on_release=self.apply_exit_penalty)
        btn_layout.add_widget(btn_yes)
        btn_no = RoundedButton(text="Продолжить игру", background_color=(0.2, 0.6, 0.2, 1))
        btn_no.bind(on_release=lambda x: self.exit_popup.dismiss())
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        self.exit_popup = Popup(title="Выход из ранга", content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
        self.exit_popup.open()

    def apply_exit_penalty(self, instance):
        self.stop_timer()
        self.stop_polling()
        app = App.get_running_app()
        if app.is_online and app.online_room_id:
            winner = app.online_opponent
            req_body = json.dumps({"room_id": app.online_room_id, "winner": winner, "is_ranked": app.is_ranked})
            def send_result(req, res):
                if res and 'players' in res:
                    if app.current_user == res['players'][0]: app.player_elo = res['new_elo_p1']
                    else: app.player_elo = res['new_elo_p2']
                    app.save_user_data()
            UrlRequest(f"{SERVER_URL}/finish_game", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=send_result)
        else:
            penalty = app.calculate_loss_penalty() + 10
            app.player_elo = max(0, app.player_elo - penalty)
            app.save_user_data()
            req_body = json.dumps({"login": app.current_user, "elo_change": -penalty})
            UrlRequest(f"{SERVER_URL}/update_bot_elo", req_body=req_body, req_headers={'Content-Type': 'application/json'})
        app.save_active_game(False)
        self.exit_popup.dismiss()
        self.exit_to_menu()

    def exit_to_menu(self):
        App.get_running_app().bot_gen += 1
        self.bot_thinking = False
        self.stop_polling()
        self.stop_timer()
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
        content.add_widget(Label(text="Выберите фигуру:"))
        btn_layout = BoxLayout(spacing=dp(10))
        for pr in ['Q', 'R', 'B', 'N']:
            btn = RoundedButton(text=pr, font_size=dp(30), font_name='ChessFont', background_color=(0.2, 0.5, 0.8, 1))
            btn.bind(on_release=lambda x, p=pr: self.finish_promotion(m, p))
            btn_layout.add_widget(btn)
        content.add_widget(btn_layout)
        self.popup = Popup(title="Превращение", content=content, size_hint=(0.8, 0.4))
        self.popup.open()

    def finish_promotion(self, m, pr):
        self.popup.dismiss()
        new_m = (m[0], m[1], m[2], m[3], pr, m[5])
        self.make_move(new_m)

    def make_move(self, m):
        self.history.append((copy_state(self.state), self.last_move))
        self.state = apply_move(self.state, m)
        self.last_move = m
        self.selected = None
        self.legal_targets = []
        app = App.get_running_app()
        self.stop_timer()
        app.play_sound()
        if app.is_online:
            UrlRequest(f"{SERVER_URL}/make_move", req_body=json.dumps({
                "room_id": app.online_room_id, "login": app.current_user, "board_data": json.dumps(self.state) 
            }), req_headers={'Content-Type': 'application/json'}, on_failure=lambda r, e: None)
        self.update_ui()
        if not app.is_online and app.game_mode == 'bot' and game_status(self.state) is None and self.state['turn'] == 'b':
            self.start_bot()
        elif app.is_online or app.is_ranked:
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
    last_seen_notification = None 

    def build(self):
        self.init_audio()
        sm = ScreenManager()
        sm.add_widget(LoadingScreen(name='loading'))
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(MainMenuScreen(name='main_menu'))
        sm.add_widget(TwoPlayersMenuScreen(name='two_players_menu'))
        sm.add_widget(BotMenuScreen(name='bot_menu'))
        sm.add_widget(RankedMenuScreen(name='ranked_menu'))
        
        self.game_screen = GameScreen(name='game')
        sm.add_widget(self.game_screen)
        
        sm.current = 'loading'
        Clock.schedule_once(lambda dt: sm.get_screen('loading').go_next(None), 3)
        return sm

    def on_start(self):
        self.check_pending_crash_penalty()

    def on_stop(self):
        if self.current_user and self.is_ranked and not self.is_offline:
            status = game_status(self.game_screen.state)
            if status is None:
                penalty = self.calculate_loss_penalty() + 50
                path = os.path.join(self.user_data_dir, 'pending_penalty.json')
                try:
                    with open(path, 'w') as f:
                        json.dump({'penalty': penalty}, f)
                except: pass
                self.save_active_game(False)
                
        if self.is_online and self.online_room_id:
            UrlRequest(f"{SERVER_URL}/leave_match", req_body=json.dumps({"login": self.current_user}), req_headers={'Content-Type': 'application/json'})

    def check_pending_crash_penalty(self):
        path = os.path.join(self.user_data_dir, 'pending_penalty.json')
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                penalty = data.get('penalty', 0)
                if penalty > 0:
                    self.player_elo = max(0, self.player_elo - penalty)
                    self.save_user_data()
                    if not self.is_offline and self.current_user:
                        req_body = json.dumps({"login": self.current_user, "elo_change": -penalty})
                        UrlRequest(f"{SERVER_URL}/update_bot_elo", req_body=req_body, req_headers={'Content-Type': 'application/json'})
                    content = BoxLayout(orientation='vertical', padding=dp(10))
                    content.add_widget(Label(text=f"Вы принудительно закрыли игру!\n\nПотеряно {penalty} ЭЛО.\nВаш рейтинг: {self.player_elo}", halign="center"))
                    popup = Popup(title="Штраф", content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
                    btn = RoundedButton(text="Понятно", size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.2, 1))
                    btn.bind(on_release=popup.dismiss)
                    content.add_widget(btn)
                    popup.open()
                os.remove(path)
            except: pass

    def save_active_game(self, active):
        path = os.path.join(self.user_data_dir, 'active_game.json')
        try:
            with open(path, 'w') as f:
                json.dump({'active': active, 'is_ranked': self.is_ranked}, f)
        except: pass

    def calculate_loss_penalty(self):
        base = {1: 12, 2: 25, 3: 37}.get(self.bot_diff, 12)
        elo = self.player_elo
        if elo <= 400: return max(5, base - 5)
        elif elo <= 500: return base
        elif elo >= 600:
            extra = ((elo - 600) // 100 + 1) * 5
            return base + extra
        return base

    def save_session(self):
        path = os.path.join(self.user_data_dir, 'session.json')
        try:
            with open(path, 'w') as f:
                json.dump({'login': self.current_user}, f)
        except: pass

    def load_session(self):
        path = os.path.join(self.user_data_dir, 'session.json')
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    login = data.get('login')
                    if login:
                        self.current_user = login
                        return True
            except: pass
        return False

    def logout_session(self):
        path = os.path.join(self.user_data_dir, 'session.json')
        if os.path.exists(path):
            try: os.remove(path)
            except: pass

    def get_db_path(self):
        return os.path.join(self.user_data_dir, 'users.json')

    def load_db(self):
        path = self.get_db_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_db(self, db):
        path = self.get_db_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(db, f)
        except: pass

    def save_user_data(self):
        if self.current_user and not self.is_offline:
            db = self.load_db()
            if self.current_user not in db:
                db[self.current_user] = {}
            db[self.current_user]['elo'] = self.player_elo
            self.save_db(db)

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
                with open(path, 'wb') as f:
                    f.write(buf.getvalue())
            except: pass
            
        try:
            if os.path.exists(path):
                self.sound_move = SoundLoader.load(path)

            self.bg_music = SoundLoader.load('music.ogg')
            if self.bg_music:
                self.bg_music.loop = True
                self.bg_music.volume = 0.3
                self.play_music()
        except:
            pass

    def play_music(self):
        if self.bg_music and self.bg_music.state != 'play':
            self.bg_music.play()

    def stop_music(self):
        if self.bg_music and self.bg_music.state == 'play':
            self.bg_music.stop()

    def play_sound(self):
        if self.sound_move:
            self.sound_move.play()

if __name__ == '__main__':
    ChessApp().run()
