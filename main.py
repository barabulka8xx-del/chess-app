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
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.animation import Animation
from kivy.network.urlrequest import UrlRequest
from kivy.graphics import Color, RoundedRectangle, Ellipse, Rectangle

# Регистрация кастомного шрифта для фигур
LabelBase.register(name='ChessFont', fn_regular='DejaVuSans.ttf')

# АДРЕС СЕРВЕРА (наш FastAPI на Waifly)
SERVER_URL = "http://node.waifly.com:27402"
# ССЫЛКА НА САЙТ ДЛЯ СКАЧИВАНИЯ (GitHub Pages)
SITE_URL = "https://barabulka8xx-del.github.io/chess-site/" 

# ТЕКУЩАЯ ВЕРСИЯ ИГРЫ (если сервер требует обновления, игра заблокирует ранговый поиск)
GAME_VERSION = "1.0"

# ================== КАСТОМНЫЕ ЭЛЕМЕНТЫ UI ==================

class RoundedButton(Button):
    """Кнопка с закругленными углами и правильным цветом фона."""
    def __init__(self, **kwargs):
        # Вытаскиваем переданный цвет фона, если нет - ставим темно-серый
        bg_col = kwargs.pop('background_color', (0.4, 0.4, 0.4, 1))
        
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        
        # Скрываем стандартный прямоугольный фон Kivy, чтобы были видны скругления
        self.background_color = (0, 0, 0, 0)
        
        with self.canvas.before:
            self.bg_color = Color(rgba=bg_col)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
            
        self.bind(pos=self.update_rect, size=self.update_rect)
        
    def update_rect(self, *args):
        """Обновляем позицию прямоугольника при изменении размера экрана."""
        self.rect.pos = self.pos
        self.rect.size = self.size


class SquareButton(Button):
    """Кнопка для клетки шахматной доски. Рисует цвет клетки и черную точку (подсказку)."""
    def __init__(self, r, c, **kwargs):
        super().__init__(**kwargs)
        self.r = r
        self.c = c
        self.font_size = dp(32)
        self.font_name = 'ChessFont'
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        
        with self.canvas.before:
            self.sq_color = Color(rgba=(0.93, 0.84, 0.72, 1)) # Светлая клетка по умолчанию
            self.sq_rect = Rectangle(pos=self.pos, size=self.size)
            self.dot_color = Color(0, 0, 0, 0) # Точка (прозрачная изначально)
            self.dot = Ellipse(size=(0, 0))
            
        self.bind(pos=self.update_graphics, size=self.update_graphics)
        
    def update_graphics(self, *args):
        """Отрисовка фона клетки и точки по центру."""
        self.sq_rect.pos = self.pos
        self.sq_rect.size = self.size
        
        dot_size = self.width * 0.25
        self.dot.size = (dot_size, dot_size)
        self.dot.pos = (self.center_x - dot_size/2, self.center_y - dot_size/2)
        
    def set_bg_color(self, color):
        """Установка цвета клетки (для подсветки хода)."""
        self.sq_color.rgba = color
        
    def show_dot(self, visible):
        """Показать/скрыть точку (куда можно сходить)."""
        if visible:
            self.dot_color.rgba = (0, 0, 0, 0.5)
        else:
            self.dot_color.rgba = (0, 0, 0, 0)


# ================== ЛОГИКА ШАХМАТ ==================

# Смещения для коня
KNIGHT_OFF = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
# Ортогональные направления (ладья, ферзь)
ORTHO = [(-1,0),(1,0),(0,-1),(0,1)]
# Диагональные направления (слон, ферзь)
DIAG  = [(-1,-1),(-1,1),(1,-1),(1,1)]

def inb(r, c): 
    """Проверка, находится ли клетка в пределах доски (0-7)."""
    return 0 <= r < 8 and 0 <= c < 8

def start_state():
    """Создание начального состояния доски."""
    return {
        'board': [
            ['r','n','b','q','k','b','n','r'], ['p']*8, # Черные (верх)
            ['.']*8, ['.']*8, ['.']*8, ['.']*8,         # Пустые клетки
            ['P']*8, ['R','N','B','Q','K','B','N','R'], # Белые (низ)
        ],
        'turn': 'w', 'castle_wk': True, 'castle_wq': True,
        'castle_bk': True, 'castle_bq': True, 'ep': None, 'halfmove': 0,
    }

def copy_state(s):
    """Глубокая копия состояния доски (чтобы не менять оригинал при просчетах бота)."""
    return {
        'board': [row[:] for row in s['board']], 'turn': s['turn'],
        'castle_wk': s['castle_wk'], 'castle_wq': s['castle_wq'],
        'castle_bk': s['castle_bk'], 'castle_bq': s['castle_bq'],
        'ep': s['ep'], 'halfmove': s['halfmove'],
    }

def is_attacked(b, r, c, by_white):
    """Проверяет, атакована ли клетка (r, c) фигурами цвета by_white."""
    # Проверка атаки коней
    for dr, dc in KNIGHT_OFF:
        nr, nc = r+dr, c+dc
        if inb(nr,nc):
            p = b[nr][nc]
            if by_white and p=='N': return True
            if not by_white and p=='n': return True
            
    # Проверка атаки пешек
    if by_white:
        for dc in (-1,1):
            nr, nc = r+1, c+dc
            if inb(nr,nc) and b[nr][nc]=='P': return True
    else:
        for dc in (-1,1):
            nr, nc = r-1, c+dc
            if inb(nr,nc) and b[nr][nc]=='p': return True
            
    # Проверка атаки ладьи/ферзя (по прямым)
    for dr, dc in ORTHO:
        nr, nc = r+dr, c+dc
        while inb(nr,nc):
            p = b[nr][nc]
            if p != '.':
                if by_white and p in 'RQ': return True
                if not by_white and p in 'rq': return True
                break
            nr += dr; nc += dc
            
    # Проверка атаки слона/ферзя (по диагоналям)
    for dr, dc in DIAG:
        nr, nc = r+dr, c+dc
        while inb(nr,nc):
            p = b[nr][nc]
            if p != '.':
                if by_white and p in 'BQ': return True
                if not by_white and p in 'bq': return True
                break
            nr += dr; nc += dc
            
    # Проверка атаки короля (вокруг на 1 клетку)
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
    """Находит координаты короля заданного цвета."""
    k = 'K' if color=='w' else 'k'
    for r in range(8):
        for c in range(8):
            if b[r][c] == k: return (r,c)
    return None

def in_check(s, color):
    """Проверяет, находится ли король цвета color под шахом."""
    kp = find_king(s['board'], color)
    return kp is not None and is_attacked(s['board'], kp[0], kp[1], color=='b')

def slide(b, r, c, turn, moves, dirs):
    """Вспомогательная функция для генерации ходов ладьи, слона и ферзя."""
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
    """Генерация ходов пешки (включая взятие на проходе и превращение)."""
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
    """Генерация всех псевдо-легальных ходов (без учета шаха)."""
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
                # Рокировка
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
    """Применяет ход к доске и возвращает новое состояние (не меняя старое)."""
    ns = copy_state(s)
    b = ns['board']
    fr, fc, tr, tc, promo, sp = m
    piece = b[fr][fc]
    color = 'w' if piece.isupper() else 'b'
    captured = b[tr][tc]
    
    # Обновляем флаги рокировки
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
    # Взятие на проходе
    if piece.upper()=='P' and abs(tr-fr)==2:
        ns['ep'] = ((fr+tr)//2, fc)
    if sp=='ep':
        if color=='w': b[tr+1][tc] = '.'
        else: b[tr-1][tc] = '.'
        
    # Перемещение фигуры
    b[tr][tc] = promo if promo else piece
    b[fr][fc] = '.'
    
    # Движение ладьи при рокировке
    if sp=='O-O':
        if color=='w': b[7][5]=b[7][7]; b[7][7]='.'
        else: b[0][5]=b[0][7]; b[0][7]='.'
    elif sp=='O-O-O':
        if color=='w': b[7][3]=b[7][0]; b[7][0]='.'
        else: b[0][3]=b[0][0]; b[0][0]='.'
        
    # Смена очереди хода
    ns['turn'] = 'b' if color=='w' else 'w'
    
    # Счетчик ходов для правила 50 ходов
    pawn_or_cap = (piece.upper()=='P') or (captured != '.')
    ns['halfmove'] = 0 if pawn_or_cap else s['halfmove']+1
    return ns

def legal_moves(s):
    """Возвращает только те ходы, после которых свой король не остается под шахом."""
    turn = s['turn']
    return [m for m in gen_pseudo(s) if not in_check(apply_move(s, m), turn)]

def game_status(s):
    """Определяет статус игры: мат, пат или игра продолжается."""
    if not legal_moves(s):
        return 'checkmate' if in_check(s, s['turn']) else 'stalemate'
    if s['halfmove'] >= 100: return 'draw50'
    return None

# ================== БОТ (МИНИМАКС) ==================

# Ценность фигур для оценки позиции
PIECE_VAL = {'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000}

def evaluate_board(s):
    """Оценивает позицию. Плюс - перевес белых, минус - черных."""
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
    """Алгоритм Минимакс с альфа-бета отсечением для просчета ходов."""
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
    """Выбирает лучший ход для бота. На легком уровне ходит случайно."""
    moves = legal_moves(s)
    if not moves: return None
    if difficulty == 1: return random.choice(moves)
    
    best_move = moves[0]; best_val = float('inf')
    for m in moves:
        # Небольшая доля рандома, чтобы бот не играл всегда одинаково
        val = minimax(apply_move(s, m), 2, -float('inf'), float('inf'), True)
        val += random.randint(-10, 10)
        if val < best_val: 
            best_val = val
            best_move = m
    return best_move
    # ================== ЭКРАНЫ ПРИЛОЖЕНИЯ ==================

class LoadingScreen(Screen):
    """Экран загрузки (Splash Screen). Показывает иконку и анимацию, пока грузятся библиотеки."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        main_layout = FloatLayout()
        
        # Фоновая картинка (наша иконка), растянутая на весь экран
        self.bg_image = Image(source='icon.png', allow_stretch=True, keep_ratio=False, size_hint=(1, 1), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        main_layout.add_widget(self.bg_image)
        
        # Текст загрузки в самом низу
        ui_layout = BoxLayout(orientation='vertical', size_hint=(1, 1), padding=dp(20))
        ui_layout.add_widget(Label(size_hint_y=0.85)) 
        self.status = Label(text="Загрузка...", font_size=dp(24), color=(1,1,1,1), size_hint_y=0.15)
        ui_layout.add_widget(self.status)
        
        main_layout.add_widget(ui_layout)
        self.add_widget(main_layout)
        
        # Анимация пульсации фона (плавное затухание и появление)
        self.anim = Animation(opacity=0.6, duration=1.0) + Animation(opacity=1.0, duration=1.0)
        self.anim.repeat = True
        self.anim.start(self.bg_image)

    def go_next(self, dt):
        """Вызывается по таймеру. Проверяет сессию и перекидывает на нужный экран."""
        self.anim.stop(self.bg_image)
        app = App.get_running_app()
        if app.load_session(): 
            self.manager.current = 'main_menu' # Если уже входил ранее
        else: 
            self.manager.current = 'login'     # Если нужно авторизоваться


class BackgroundScreen(Screen):
    """Базовый класс для меню, который автоматически добавляет фоновую картинку."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_layout = FloatLayout()
        # Наш размытый фон с шахматной доской
        self.bg = Image(source='menu_bg.png', allow_stretch=True, keep_ratio=False, size_hint=(1, 1), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.main_layout.add_widget(self.bg)
        self.add_widget(self.main_layout)


class ChessBoard(GridLayout):
    """Визуальная сетка 8x8, состоящая из кнопок-клеток."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 8
        self.rows = 8
        self.squares = {}
        self.build_board()

    def build_board(self):
        """Создает 64 кнопки и раскрашивает их в шахматном порядке."""
        for r in range(8):
            for c in range(8):
                color = (0.93, 0.84, 0.72, 1) if (r+c)%2==0 else (0.71, 0.53, 0.39, 1)
                btn = SquareButton(r, c, text="", background_color=color)
                btn.bind(on_release=self.on_square_click)
                self.squares[(r,c)] = btn
                self.add_widget(btn)

    def on_square_click(self, instance):
        """Передает клик по клетке в главный класс игры."""
        app = App.get_running_app()
        app.game_screen.handle_square_click(instance.r, instance.c)

    def update_board(self, board, selected, legal_targets, last_move):
        """Перерисовывает доску: ставит фигуры, подсвечивает ходы и выбранную клетку."""
        # Сброс всех клеток в исходный цвет
        for (r, c), btn in self.squares.items():
            base_color = (0.93, 0.84, 0.72, 1) if (r+c)%2==0 else (0.71, 0.53, 0.39, 1)
            btn.set_bg_color(base_color)
            btn.text = ""
            btn.show_dot(False)
            
        # Словарь для перевода букв (в коде) в красивые символы Unicode
        piece_map = {'K':'♚','Q':'♛','R':'♜','B':'♝','N':'♞','P':'♟', 'k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}
        
        # Расставляем фигуры
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p != '.':
                    btn = self.squares[(r,c)]
                    btn.text = piece_map.get(p, p)
                    btn.color = (1, 1, 1, 1) if p.isupper() else (0, 0, 0, 1)

        # Подсветка последнего хода (желтоватый цвет)
        if last_move:
            for rr, cc in (last_move[0:2], last_move[2:4]):
                self.squares[(rr,cc)].set_bg_color((0.8, 0.8, 0.4, 1))
                
        # Подсветка выбранной фигуры (золотистый)
        if selected:
            self.squares[selected].set_bg_color((0.96, 0.84, 0.43, 1))
            
        # Показ черных точек там, куда можно сходить
        for m in legal_targets:
            tr, tc = m[2], m[3]
            self.squares[(tr,tc)].show_dot(True)


class LoginScreen(BackgroundScreen):
    """Экран авторизации и регистрации, а также офлайн-режима."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = 'login' # Текущий режим: 'login' или 'register'
        
        # Основной контейнер
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
        
        # Подсказка внизу
        info_label = Label(text="(i) для регистрации потребуется интернет", font_size=dp(11), color=(0.7, 0.7, 0.7, 1), size_hint_y=0.05)
        layout.add_widget(info_label)
        
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        """Включаем музыку при входе на экран."""
        App.get_running_app().play_music()

    def play_offline(self, instance):
        """Вход в игру без интернета и без аккаунта."""
        app = App.get_running_app()
        app.is_offline = True
        app.current_user = "Гость"
        app.player_elo = 0
        app.logout_session() # Чтобы при следующем запуске снова попросило войти
        self.manager.current = 'main_menu'

    def toggle_mode(self, instance):
        """Переключение между входом и регистрацией."""
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
        """Отправка данных на сервер."""
        login = self.login_input.text.strip()
        password = self.pass_input.text.strip()
        
        # Проверки на пустоту и недопустимые символы
        if not login or not password:
            self.status_label.text = "Заполните все поля!"
            return
        if not re.match(r'^[A-Za-z0-9_$#.]{3,20}$', login):
            self.status_label.text = "Недопустимые символы в логине!"
            return
            
        self.status_label.text = "Подключение к серверу..."
        self.status_label.color = (1, 1, 0, 1)
        self.submit_btn.disabled = True # Блокируем кнопку, чтобы не спамили
        
        app = App.get_running_app()
        app.is_offline = False
        req_body = json.dumps({"login": login, "password": password})
        req_headers = {'Content-Type': 'application/json'}

        if self.mode == 'login':
            def on_success(req, result):
                self.submit_btn.disabled = False
                app.current_user = login
                app.player_elo = result.get('elo', 300) # Забираем ЭЛО с сервера
                app.save_session()
                self.manager.current = 'main_menu'
                
            def on_error(req, error):
                self.submit_btn.disabled = False
                self.status_label.color = (1, 0.3, 0.3, 1)
                self.status_label.text = "Неверный пароль" if req.resp_status == 401 else "Ошибка сервера или нет сети"

            UrlRequest(f"{SERVER_URL}/login", req_body=req_body, req_headers=req_headers, on_success=on_success, on_error=on_error, timeout=10)
            
        else:
            def on_success(req, result):
                self.submit_btn.disabled = False
                self.status_label.color = (0, 1, 0, 1)
                self.status_label.text = "Успешно! Теперь войдите."
                self.toggle_mode(None) # Сбрасываем на экран входа
                
            def on_error(req, error):
                self.submit_btn.disabled = False
                self.status_label.color = (1, 0.3, 0.3, 1)
                self.status_label.text = "Этот логин уже занят!" if req.resp_status == 400 else "Ошибка сервера или нет сети"

            UrlRequest(f"{SERVER_URL}/register", req_body=req_body, req_headers=req_headers, on_success=on_success, on_error=on_error, timeout=10)


class MainMenuScreen(BackgroundScreen):
    """Главное меню игры."""
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
        
        # Кнопка админа (будет видна только аккаунту DEV$DEV)
        self.admin_btn = RoundedButton(text="📢 Отправить уведомление", font_size=dp(14), size_hint_y=0.08, background_color=(0.8, 0.2, 0.8, 1))
        self.admin_btn.bind(on_release=self.show_admin_panel)
        ui_layout.add_widget(self.admin_btn)
        
        btn_logout = RoundedButton(text="Выйти", font_size=dp(14), size_hint_y=0.08, background_color=(0.5, 0.2, 0.2, 1))
        btn_logout.bind(on_release=self.logout)
        ui_layout.add_widget(btn_logout)
        
        ui_layout.add_widget(Label(size_hint_y=0.05))
        
        # Версия игры и подпись
        ui_layout.add_widget(Label(text=f"v{GAME_VERSION}", font_size=dp(10), color=(0.5, 0.5, 0.5, 1), size_hint_y=0.05))
        ui_layout.add_widget(Label(text="Сделано Kirillom Der**", font_size=dp(12), color=(0.7, 0.7, 0.7, 1), size_hint_y=0.05))
        
        self.main_layout.add_widget(ui_layout)

    def on_pre_enter(self, *args):
        """Обновляем данные при каждом входе в меню."""
        app = App.get_running_app()
        self.user_label.text = f"Вы вошли как: {app.current_user}"
        
        # Проверка на админа
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
            # Синхронизация ЭЛО с сервером (чтобы не было расхождений)
            def sync_success(req, result):
                app.player_elo = result.get('elo', app.player_elo)
                app.save_user_data()
                self.elo_label.text = f"Ваш ЭЛО: {app.player_elo}"
                self.elo_label.color = (1, 0.8, 0.2, 1)
                
            UrlRequest(f"{SERVER_URL}/sync_elo/{app.current_user}", on_success=sync_success)
            
            # Проверка уведомлений от разработчика
            self.check_developer_notification()
            
        app.play_music()

    def show_admin_panel(self, instance):
        """Панель управления уведомлениями для разработчика."""
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
                App.get_running_app().last_seen_notification = None # Сбрасываем память
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
        """Проверяет, нет ли активных уведомлений от разработчика на сервере."""
        def on_success(req, result):
            app = App.get_running_app()
            if result and result.get('active'):
                msg = result.get('message', '')
                # Показываем окно только если это новое уведомление
                if msg and msg != app.last_seen_notification:
                    app.last_seen_notification = msg
                    
                    content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
                    content.add_widget(Label(text=msg, halign="center", font_size=dp(18)))
                    
                    btn_layout = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(50))
                    
                    btn_old = RoundedButton(text="Играть на старой", background_color=(0.3, 0.3, 0.3, 1))
                    btn_old.bind(on_release=lambda x: popup.dismiss())
                    btn_layout.add_widget(btn_old)
                    
                    btn_new = RoundedButton(text="Скачать новую", background_color=(0.2, 0.6, 0.2, 1))
                    
                    def open_site(instance):
                        popup.dismiss()
                        webbrowser.open(SITE_URL) # Перекидываем на GitHub Pages
                        
                    btn_new.bind(on_release=open_site)
                    btn_layout.add_widget(btn_new)
                    
                    content.add_widget(btn_layout)
                    popup = Popup(title="Обновление!", content=content, size_hint=(0.85, 0.4), auto_dismiss=False)
                    popup.open()

        UrlRequest(f"{SERVER_URL}/get_notification", on_success=on_success)

    def logout(self, instance):
        """Выход из аккаунта."""
        app = App.get_running_app()
        app.current_user = None
        app.player_elo = 300
        app.is_offline = False
        app.logout_session()
        self.manager.current = 'login'

    def start_bot_menu(self):
        """Переход в меню выбора сложности бота."""
        app = App.get_running_app()
        app.is_ranked = False
        app.is_online = False
        self.manager.current = 'bot_menu'

    def start_ranked(self):
        """Проверка на онлайн перед переходом в ранговое меню."""
        app = App.get_running_app()
        if app.is_offline:
            Popup(title="Офлайн", content=Label(text="Ранговые матчи недоступны\nбез интернета."), size_hint=(0.8, 0.3)).open()
            return
        self.manager.current = 'ranked_menu'


class TwoPlayersMenuScreen(BackgroundScreen):
    """Меню для игры на двоих: локально или онлайн по коду."""
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
        """Запуск игры на одном устройстве (2p)."""
        app = App.get_running_app()
        app.is_ranked = False
        app.is_online = False
        app.game_mode = '2p'
        app.game_screen.new_game()
        self.manager.current = 'game'

    def show_room_menu(self, instance):
        """Окно создания/входа в комнату по коду."""
        app = App.get_running_app()
        if app.is_offline:
            Popup(title="Офлайн", content=Label(text="Онлайн по коду недоступен\nбез интернета."), size_hint=(0.8, 0.3)).open()
            return

        # Сначала пингуем сервер, чтобы убедиться, что он живой
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
                self.poll_join(result['room_id']) # Начинаем ждать второго игрока

            def join_req(req, result):
                self.room_popup.dismiss()
                app.is_online = True
                app.is_ranked = False
                app.online_room_id = code_input.text.upper()
                app.online_color = 'black'
                app.online_opponent = result.get('opponent', 'Соперник')
                app.game_screen.new_game()
                self.manager.current = 'game'

            btn_create.bind(on_release=lambda x: UrlRequest(f"{SERVER_URL}/create_room", req_body=json.dumps({"login": app.current_user}), req_headers={'Content-Type': 'application/json'}, on_success=create_req))
            btn_join.bind(on_release=lambda x: UrlRequest(f"{SERVER_URL}/join_room", req_body=json.dumps({"login": app.current_user, "room_code": code_input.text.upper()}), req_headers={'Content-Type': 'application/json'}, on_success=join_req, on_error=lambda req, err: Popup(title="Ошибка", content=Label(text="Комната не найдена"), size_hint=(0.8, 0.3)).open()))
            
            self.room_popup.open()

        UrlRequest(f"{SERVER_URL}/ping", on_success=ping_success, on_error=lambda r, e: Popup(title="Нет сети", content=Label(text="Сервер недоступен."), size_hint=(0.8, 0.3)).open(), timeout=5)

    def poll_join(self, room_id):
        """Ожидание, пока второй игрок зайдет в комнату."""
        app = App.get_running_app()
        def check(req, result):
            if result.get('board_data') is not None: # Как только сервер получил первый ход, начинаем игру
                app.is_online = True
                app.is_ranked = False
                app.online_room_id = room_id
                app.online_color = 'white'
                app.game_screen.new_game()
                self.manager.current = 'game'
            else: 
                Clock.schedule_once(lambda dt: self.poll_join(room_id), 2)
        UrlRequest(f"{SERVER_URL}/get_move/{room_id}", on_success=check)
        class RankedMenuScreen(BackgroundScreen):
    """Экран поиска рангового соперника."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_searching = False # Флаг, чтобы понимать, идет ли сейчас поиск
        
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
        
        # Текст для отображения статуса сервера (онлайн/офлайн)
        self.server_status_label = Label(text="проверка сервера...", font_size=dp(12), color=(1, 1, 0, 1), size_hint_y=0.1)
        layout.add_widget(self.server_status_label)
        
        self.main_layout.add_widget(layout)

    def on_pre_enter(self, *args):
        """При входе на экран запускаем музыку и проверяем сервер."""
        App.get_running_app().play_music()
        self.check_server_status()

    def check_server_status(self):
        """Пингуем сервер, чтобы узнать, работает ли он."""
        def on_success(req, result):
            self.server_status_label.text = "сервер онлайн"
            self.server_status_label.color = (0, 1, 0, 1) # Зеленый

        def on_error(req, error):
            self.server_status_label.text = "сервер офлайн"
            self.server_status_label.color = (1, 0, 0, 1) # Красный

        UrlRequest(f"{SERVER_URL}/ping", on_success=on_success, on_error=on_error, timeout=5)

    def find_online_match(self, instance):
        """Начинает поиск соперника по ЭЛО."""
        app = App.get_running_app()
        
        # Сначала пингуем, чтобы убедиться, что интернет есть
        def ping_success(req, result):
            self.is_searching = True
            
            # Окно ожидания
            content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
            content.add_widget(Label(text="Ищем соперника...\nПодождите."))
            
            btn_cancel = RoundedButton(text="Отменить поиск", size_hint_y=None, height=dp(50), background_color=(0.8, 0.2, 0.2, 1))
            btn_cancel.bind(on_release=self.cancel_search)
            content.add_widget(btn_cancel)
            
            self.waiting_popup = Popup(title="Поиск", content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
            self.waiting_popup.open()
            
            def on_success(req, result):
                if not self.is_searching: return
                if result.get('status') == 'waiting': 
                    # Если сервер говорит "ждем", проверяем статус через 2 секунды
                    Clock.schedule_once(lambda dt: self.check_match_status(app), 2)
                elif result.get('status') == 'matched':
                    # Если нашли соперника, запускаем игру
                    self.is_searching = False
                    self.start_online_game(result['room_id'], result['color'], result['opponent'], result.get('opponent_elo', 300))
                    
            def on_error(req, error):
                self.waiting_popup.dismiss()
                self.is_searching = False
                
                # ЕСЛИ СЕРВЕР ВЕРНУЛ 403 (ЗНАЧИТ ВЕРСИЯ УСТАРЕЛА)
                if req.resp_status == 403:
                    content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
                    content.add_widget(Label(text="Вышло обновление игры!\nПожалуйста, скачайте новую версию, чтобы играть в ранговый матч.", halign="center", font_size=dp(16)))
                    
                    btn = RoundedButton(text="Скачать обновление", size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.2, 1))
                    
                    def open_site(instance):
                        self.update_popup.dismiss()
                        webbrowser.open(SITE_URL) # Перекидываем на сайт
                        
                    btn.bind(on_release=open_site)
                    content.add_widget(btn)
                    
                    self.update_popup = Popup(title="Обновление", content=content, size_hint=(0.85, 0.4), auto_dismiss=False)
                    self.update_popup.open()
                else: 
                    Popup(title="Ошибка", content=Label(text="Сервер недоступен"), size_hint=(0.8, 0.3)).open()

            # Отправляем запрос на поиск, передавая версию игры!
            req_body = json.dumps({
                "login": app.current_user, 
                "elo": app.player_elo, 
                "version": GAME_VERSION
            })
            UrlRequest(f"{SERVER_URL}/find_match", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=on_success, on_error=on_error)

        UrlRequest(f"{SERVER_URL}/ping", on_success=ping_success, on_error=lambda r, e: Popup(title="Нет сети", content=Label(text="Проверьте интернет."), size_hint=(0.8, 0.3)).open(), timeout=5)

    def cancel_search(self, instance):
        """Отмена поиска соперника."""
        self.is_searching = False
        self.waiting_popup.dismiss()
        app = App.get_running_app()
        # Говорим серверу выкинуть нас из очереди
        UrlRequest(f"{SERVER_URL}/cancel_search", req_body=json.dumps({"login": app.current_user}), req_headers={'Content-Type': 'application/json'})

    def check_match_status(self, app):
        """Повторная проверка статуса поиска (если сразу никого не нашли)."""
        if not self.is_searching: return
        if not getattr(self.waiting_popup, '_window', None): return
        
        def on_success(req, result):
            if not self.is_searching: return
            if result.get('status') == 'matched':
                self.is_searching = False
                self.start_online_game(result['room_id'], result['color'], result['opponent'], result.get('opponent_elo', 300))
            elif result.get('status') == 'waiting':
                # Отправляем повторный запрос на поиск для обновления таймера ожидания на сервере
                req_body = json.dumps({"login": app.current_user, "elo": app.player_elo, "version": GAME_VERSION})
                UrlRequest(f"{SERVER_URL}/find_match", req_body=req_body, req_headers={'Content-Type': 'application/json'}, 
                           on_success=lambda r, res: Clock.schedule_once(lambda dt: self.check_match_status(app), 2))

        UrlRequest(f"{SERVER_URL}/check_match/{app.current_user}", on_success=on_success)

    def start_online_game(self, room_id, color, opponent, opp_elo):
        """Переход на экран игры, когда соперник найден."""
        self.waiting_popup.dismiss()
        app = App.get_running_app()
        app.is_online = True
        app.is_ranked = True
        app.game_mode = 'bot' # Используем логику, чтобы не дублировать код (бот просто не будет ходить)
        app.online_room_id = room_id
        app.online_color = color
        app.online_opponent = opponent
        app.online_opponent_elo = opp_elo
        
        app.game_screen.new_game()
        self.manager.current = 'game'
        
        # Оповещаем игрока о начале игры
        popup = Popup(title="Игра началась", content=Label(text=f"Соперник: {opponent} ({opp_elo} ЭЛО)\nВаш цвет: {'Белые' if color == 'white' else 'Черные'}"), size_hint=(0.8, 0.3))
        popup.open()

    def start_ranked_bot(self, instance):
        """Запуск игры с ботом в ранговом режиме (с учетом ЭЛО)."""
        app = App.get_running_app()
        elo = app.player_elo
        
        # Адаптивная сложность бота в зависимости от рейтинга игрока
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
    """Экран выбора сложности бота для обычной (не ранговой) игры."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20), size_hint=(0.9, 0.9), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        layout.add_widget(Label(text="Сложность", font_size=dp(30), size_hint_y=0.3))
        
        # Создаем кнопки для трех уровней сложности
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
        """Запуск обычной игры с ботом (без изменения ЭЛО)."""
        app = App.get_running_app()
        app.is_ranked = False
        app.is_online = False
        app.game_mode = 'bot'
        app.bot_diff = diff
        app.game_screen.new_game()
        self.manager.current = 'game'
        class GameScreen(Screen):
    """Главный экран, где происходит игра."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = start_state() # Текущее состояние доски
        self.history = []          # История для кнопки "Отмена"
        self.selected = None       # Выбранная фигура (координаты)
        self.legal_targets = []    # Ходы, куда можно сходить выбранной фигурой
        self.last_move = None      # Последний сделанный ход (для подсветки)
        self.bot_thinking = False  # Флаг, что бот сейчас думает
        
        self.game_over_triggered = False # Защита, чтобы мат не засчитался дважды
        self.exit_popup = None
        
        # Переменные для таймера (актуально для ранговых игр)
        self.time_left = 45
        self.timer_event = None
        self.poll_event = None
        
        main_layout = BoxLayout(orientation='vertical')
        
        # --- ВЕРХНЯЯ ПАНЕЛЬ С КНОПКАМИ ---
        top_bar = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(5), padding=dp(5))
        
        btn_menu = RoundedButton(text="Меню", font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        btn_menu.bind(on_release=self.go_to_menu)
        top_bar.add_widget(btn_menu)
        
        # Текст статуса (Ход белых / ШАХ / МАТ)
        self.status_label = Label(text="Ход белых", font_size=dp(16), bold=True)
        top_bar.add_widget(self.status_label)
        
        # Текст таймера
        self.timer_label = Label(text="", font_size=dp(18), bold=True, color=(1, 0.5, 0.5, 1))
        top_bar.add_widget(self.timer_label)
        
        # Кнопка отмены хода (блокируется в онлайне/ранге)
        self.btn_undo = RoundedButton(text="Отмена", font_size=dp(16), background_color=(0.3, 0.3, 0.3, 1))
        self.btn_undo.bind(on_release=self.undo_move)
        top_bar.add_widget(self.btn_undo)
        
        main_layout.add_widget(top_bar)
        
        # --- ПАНЕЛЬ С НИКАМИ И ЭЛО (для онлайна) ---
        self.match_info_layout = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(10))
        
        self.opp_label = Label(text="", font_size=dp(14), halign="left", valign="middle")
        self.opp_label.bind(size=self.opp_label.setter('text_size'))
        self.match_info_layout.add_widget(self.opp_label)
        
        self.my_label = Label(text="", font_size=dp(14), halign="right", valign="middle")
        self.my_label.bind(size=self.my_label.setter('text_size'))
        self.match_info_layout.add_widget(self.my_label)
        
        main_layout.add_widget(self.match_info_layout)
        
        # --- САМА ДОСКА (по центру) ---
        board_container = FloatLayout()
        self.board_ui = ChessBoard(size_hint=(0.95, None), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        # Привязываем высоту доски к ее ширине, чтобы она была квадратной
        self.board_ui.bind(width=lambda instance, value: setattr(instance, 'height', value))
        
        board_container.add_widget(self.board_ui)
        main_layout.add_widget(board_container)
        
        self.add_widget(main_layout)

    def on_pre_enter(self, *args):
        """Выключаем музыку при входе в игру, чтобы не мешала."""
        App.get_running_app().stop_music()

    def on_leave(self, *args):
        """Останавливаем все процессы при выходе с экрана."""
        self.stop_timer()
        self.stop_polling()

    def new_game(self):
        """Сброс всех переменных для начала новой игры."""
        self.state = start_state()
        self.history = []
        self.selected = None
        self.legal_targets = []
        self.last_move = None
        self.bot_thinking = False
        self.game_over_triggered = False
        
        app = App.get_running_app()
        
        # Показываем ники и ЭЛО, если играем онлайн в ранге
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
            self.match_info_layout.opacity = 0 # Скрываем панель в обычных играх
            
        # Настройка кнопки отмены и таймера
        if app.is_ranked or app.is_online:
            self.btn_undo.text = "Без отмены"
            self.btn_undo.disabled = True
            self.btn_undo.background_color = (0.2, 0.2, 0.2, 1)
            app.save_active_game(True) # Запоминаем, что игра идет (для защиты от вылетов)
            self.reset_timer()
        else:
            self.btn_undo.text = "Отмена"
            self.btn_undo.disabled = False
            self.btn_undo.background_color = (0.3, 0.3, 0.3, 1)
            app.save_active_game(False)
            self.stop_timer()
            self.timer_label.text = ""
            
        if app.is_online:
            self.start_polling() # Запускаем обновление доски с сервера
            
        self.update_ui()

    def start_polling(self):
        """Запуск цикла, который каждые 1.5 секунды проверяет ходы соперника на сервере."""
        self.stop_polling()
        self.poll_event = Clock.schedule_interval(self.check_server_move, 1.5)

    def stop_polling(self):
        if self.poll_event:
            self.poll_event.cancel()
            self.poll_event = None

    def check_server_move(self, dt):
        """Получает состояние доски с сервера. Если доска изменилась (соперник сходил), обновляет её."""
        app = App.get_running_app()
        if not app.is_online or not app.online_room_id: return
        
        def on_success(req, result):
            if not result or not result.get('board_data'): return
            new_state = json.loads(result['board_data'])
            
            # Если очередь хода изменилась (значит, соперник сходил), обновляем экран
            if self.state['turn'] != new_state['turn']:
                self.history.append((copy_state(self.state), self.last_move))
                self.state = new_state
                self.last_move = None
                self.selected = None
                self.legal_targets = []
                app.play_sound()
                self.update_ui()
                
                if app.is_ranked:
                    self.reset_timer()

        def on_error(req, error):
            # Если сервер отвечает 404 (комната не найдена), значит соперник вышел
            if req.resp_status == 404:
                self.stop_polling()
                self.stop_timer()
                self.game_over_triggered = True
                
                # Синхронизируем ЭЛО (оно должно было вырасти за победу)
                def sync_success(r, res):
                    app.player_elo = res.get('elo', app.player_elo)
                    app.save_user_data()
                    self.show_end_popup("ПОБЕДА!", "Соперник покинул игру.\nВам засчитана победа!\n\nВаш ЭЛО: " + str(app.player_elo))
                
                UrlRequest(f"{SERVER_URL}/sync_elo/{app.current_user}", on_success=sync_success)

        UrlRequest(f"{SERVER_URL}/get_move/{app.online_room_id}", on_success=on_success, on_error=on_error)

    def start_timer(self):
        """Запуск 45-секундного таймера (для ранга)."""
        self.stop_timer()
        app = App.get_running_app()
        if not (app.is_ranked or app.is_online): return
            
        # Проверяем, чей сейчас ход. Таймер тикает только на игрока.
        my_color = 'w' if not hasattr(app, 'online_color') else ('w' if app.online_color == 'white' else 'b')
        if self.state['turn'] != my_color: return

        self.timer_label.color = (1, 0.5, 0.5, 1)
        self.timer_label.text = f"⏳ {self.time_left}с"
        self.timer_event = Clock.schedule_interval(self.tick_timer, 1)

    def stop_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def tick_timer(self, dt):
        """Уменьшение таймера каждую секунду."""
        if game_status(self.state) is not None:
            self.stop_timer()
            return
            
        self.time_left -= 1
        
        # Последние 5 секунд подсвечиваем красным
        if self.time_left <= 5:
            self.timer_label.color = (1, 0, 0, 1)
            self.timer_label.text = f"⚠️ {self.time_left}с"
        else:
            self.timer_label.color = (1, 0.5, 0.5, 1)
            self.timer_label.text = f"⏳ {self.time_left}с"
            
        if self.time_left <= 0:
            self.stop_timer()
            self.time_out_loss()

    def reset_timer(self):
        """Сброс таймера на 45 секунд."""
        self.time_left = 45
        self.start_timer()

    def time_out_loss(self):
        """Обработка проигрыша по времени."""
        self.game_over_triggered = True
        app = App.get_running_app()
        app.save_active_game(False)
        
        if app.is_ranked:
            penalty = app.calculate_loss_penalty()
            app.player_elo = max(0, app.player_elo - penalty)
            app.save_user_data()
            
            # Отправляем штраф на сервер (игра с ботом)
            if not app.is_online:
                req_body = json.dumps({"login": app.current_user, "elo_change": -penalty})
                UrlRequest(f"{SERVER_URL}/update_bot_elo", req_body=req_body, req_headers={'Content-Type': 'application/json'})
                
            msg = f"Время вышло!\nЗасчитано как поражение.\n\n-{penalty} ЭЛО\nВаш рейтинг: {app.player_elo}"
        else: 
            msg = "Время вышло!"
            
        self.show_end_popup("ПОРАЖЕНИЕ", msg)

    def update_ui(self):
        """Обновляет доску и текст статуса."""
        self.board_ui.update_board(self.state['board'], self.selected, self.legal_targets, self.last_move)
        self.status_label.text = self.get_status_text()
        
        st = game_status(self.state)
        if st == 'checkmate' or in_check(self.state, self.state['turn']):
            self.status_label.color = (1, 0.2, 0.2, 1) # Красный при шахе/мате
        else: 
            self.status_label.color = (1, 1, 1, 1)
            
        self.check_game_over()

    def check_game_over(self):
        """Проверка на мат. Начисление ЭЛО, если игра закончена."""
        st = game_status(self.state)
        if st == 'checkmate' and not self.game_over_triggered:
            self.game_over_triggered = True
            self.stop_timer()
            self.stop_polling()
            app = App.get_running_app()
            app.save_active_game(False)
            
            # Определяем, кто выиграл
            if self.state['turn'] == 'b':
                title_text = "ПОБЕДА БЕЛЫХ!" if app.game_mode == '2p' else "ПОБЕДА!"
            else:
                title_text = "ПОБЕДА ЧЁРНЫХ!" if app.game_mode == '2p' else "ПОРАЖЕНИЕ"
                
            if app.is_online:
                # Если онлайн, отправляем результат на сервер
                winner = app.current_user if self.state['turn'] == 'b' else app.online_opponent
                req_body = json.dumps({"room_id": app.online_room_id, "winner": winner, "is_ranked": app.is_ranked})
                
                def send_result(req, res):
                    if res and 'players' in res:
                        if app.current_user == res['players'][0]: app.player_elo = res['new_elo_p1']
                        else: app.player_elo = res['new_elo_p2']
                        app.save_user_data()
                        
                UrlRequest(f"{SERVER_URL}/finish_game", req_body=req_body, req_headers={'Content-Type': 'application/json'}, on_success=send_result)
                
                if app.is_ranked: msg = "Игра окончена!\n\nЭЛО обновлено (см. в меню)."
                else: msg = "Игра окончена!\n\nВ дружеском матче ЭЛО не начисляется."
                
            elif app.is_ranked:
                # Если игра с ботом в ранге, обновляем ЭЛО и отправляем на сервер
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
                # Обычная игра (2p или простой бот) - ЭЛО не меняется
                if app.game_mode == 'bot':
                    msg = "Вы поставили мат!\n\nВ обычной игре ЭЛО не начисляется." if self.state['turn'] == 'b' else "Бот поставил вам мат.\n\nВ обычной игре ЭЛО не начисляется."
                else:
                    msg = "Игра окончена матом.\n\nВ игре на двоих ЭЛО не начисляется."
                    
            self.show_end_popup(title_text, msg)

    def show_end_popup(self, title, text):
        """Всплывающее окно в конце игры."""
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
        """Возвращает текст статуса для верхней панели."""
        if self.bot_thinking: return "Бот думает..."
        st = game_status(self.state)
        if st == 'checkmate': return "МАТ!"
        if st == 'stalemate': return "Ничья (пат)."
        if st == 'draw50': return "Ничья (50 ходов)."
        
        if in_check(self.state, self.state['turn']):
            return "ШАХ! Ход белых" if self.state['turn'] == 'w' else "ШАХ! Ход чёрных"
            
        return "Ход белых" if self.state['turn'] == 'w' else "Ход чёрных"

    def go_to_menu(self, instance):
        """Выход в меню (с проверкой на ранговую игру)."""
        app = App.get_running_app()
        if (app.is_ranked or app.is_online) and game_status(self.state) is None:
            self.show_exit_warning() # Если игра не закончена, показываем предупреждение
        else:
            self.stop_timer()
            self.stop_polling()
            self.exit_to_menu()

    def show_exit_warning(self):
        """Окно предупреждения о выходе из ранговой игры."""
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
        """Применение штрафа при выходе из ранговой игры."""
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
        """Очистка и переход в главное меню."""
        App.get_running_app().bot_gen += 1
        self.bot_thinking = False
        self.stop_polling()
        self.manager.current = 'main_menu'

    def undo_move(self, instance):
        """Отмена последнего хода (только для обычных игр)."""
        app = App.get_running_app()
        if app.is_ranked or app.is_online: return
        if game_status(self.state) is not None: return
            
        if self.history:
            self.state, self.last_move = self.history.pop()
            # Если играли с ботом, отменяем и ход бота тоже
            if app.game_mode == 'bot' and self.state['turn'] == 'b' and self.history:
                self.state, self.last_move = self.history.pop()
                
        self.selected = None
        self.legal_targets = []
        self.update_ui()

    def handle_square_click(self, r, c):
        """Обработка клика по доске."""
        if game_status(self.state) is not None: return
        app = App.get_running_app()
        
        # В онлайне проверяем, твой ли сейчас ход
        if app.is_online:
            my_color = 'w' if app.online_color == 'white' else 'b'
            if self.state['turn'] != my_color: return
        
        # В игре с ботом не даем ходить, пока бот думает
        if app.game_mode == 'bot' and not app.is_online and (self.bot_thinking or self.state['turn'] == 'b'): return

        # Если фигура уже выбрана, и кликнули по точке для хода
        if self.selected:
            for m in self.legal_targets:
                if (m[2], m[3]) == (r, c):
                    if m[4]: # Если это ход пешкой на превращение
                        self.show_promotion(m)
                        return
                    self.make_move(m)
                    return
                    
        # Выбор фигуры
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
        """Окно выбора фигуры при превращении пешки."""
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
        """Совершение хода и отправка его на сервер (если онлайн)."""
        self.history.append((copy_state(self.state), self.last_move))
        self.state = apply_move(self.state, m)
        self.last_move = m
        self.selected = None
        self.legal_targets = []
        
        app = App.get_running_app()
        self.stop_timer()
        app.play_sound()
        
        # ОТПРАВЛЯЕМ ВСЮ ДОСКУ НА СЕРВЕР
        if app.is_online:
            def on_success(req, res): pass
            UrlRequest(f"{SERVER_URL}/make_move", req_body=json.dumps({
                "room_id": app.online_room_id, 
                "login": app.current_user, 
                "board_data": json.dumps(self.state) 
            }), req_headers={'Content-Type': 'application/json'}, on_success=on_success)
            
        self.update_ui()
        
        # Если играем с ботом, запускаем его ответный ход
        if not app.is_online and app.game_mode == 'bot' and game_status(self.state) is None and self.state['turn'] == 'b':
            self.start_bot()
        elif app.is_online or app.is_ranked:
            self.reset_timer()

    def start_bot(self):
        """Запуск просчета хода бота в отдельном потоке (чтобы не вешало интерфейс)."""
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
        """Применение хода бота на доске."""
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
    """Главный класс приложения, управляющий глобальными переменными."""
    game_mode = '2p'
    bot_diff = 1
    bot_gen = 0
    sound_move = None
    bg_music = None
    
    # Данные игрока
    current_user = None
    player_elo = 300
    is_ranked = False
    is_online = False
    is_offline = False
    online_room_id = None
    online_color = 'white'
    online_opponent = None
    online_opponent_elo = 300
    last_seen_notification = None # Запоминаем, какое уведомление уже видели

    def build(self):
        """Создание менеджера экранов и запуск приложения."""
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
        
        # Через 3 секунды экран загрузки перекинет на нужный экран
        Clock.schedule_once(lambda dt: sm.get_screen('loading').go_next(None), 3)
        return sm

    def on_start(self):
        """Проверка, не вылетало ли приложение в прошлый раз."""
        self.check_pending_crash_penalty()

    def on_stop(self):
        """Вызывается при закрытии приложения."""
        # Если игрок закрыл приложение во время ранговой игры, начисляем штраф
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
                
        # Сообщаем серверу, что вышли из онлайна
        if self.is_online and self.online_room_id:
            UrlRequest(f"{SERVER_URL}/leave_match", req_body=json.dumps({"login": self.current_user}), req_headers={'Content-Type': 'application/json'})

    def check_pending_crash_penalty(self):
        """Показывает окно штрафа, если в прошлый раз приложение было закрыто принудительно."""
        path = os.path.join(self.user_data_dir, 'pending_penalty.json')
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                penalty = data.get('penalty', 0)
                if penalty > 0:
                    self.player_elo = max(0, self.player_elo - penalty)
                    self.save_user_data()
                    
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
        """Вычисление штрафа за проигрыш (зависит от ЭЛО)."""
        base = {1: 12, 2: 25, 3: 37}.get(self.bot_diff, 12)
        elo = self.player_elo
        if elo <= 400: return max(5, base - 5)
        elif elo <= 500: return base
        elif elo >= 600:
            extra = ((elo - 600) // 100 + 1) * 5
            return base + extra
        return base

    # --- РАБОТА С СЕССИЕЙ (АВТОВХОД) ---
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

    # --- ЛОКАЛЬНАЯ БАЗА ДАННЫХ (ДЛЯ КЭША ЭЛО) ---
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

    # --- АУДИО ---
    def init_audio(self):
        """Генерация звука хода (бип) и загрузка фоновой музыки."""
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
            
        if os.path.exists(path):
            self.sound_move = SoundLoader.load(path)

        self.bg_music = SoundLoader.load('music.ogg')
        if self.bg_music:
            self.bg_music.loop = True
            self.bg_music.volume = 0.3
            self.play_music()

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
