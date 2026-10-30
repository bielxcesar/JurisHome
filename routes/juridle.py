from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth.security import get_current_user
from database import get_db
from model.models import Usuario
from services import juridle

router = APIRouter(prefix='/api/juridle', tags=['Juridle'])


class Resposta(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pergunta: int = Field(strict=True, ge=0, lt=juridle.TAMANHO_RODADA)
    opcao: int = Field(strict=True, ge=0, le=3)


@router.get('/estado')
def estado(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    rodada = juridle.ativa(db, usuario.uuid)
    if rodada and rodada.expira_em <= juridle.agora():
        rodada = None
    return {'progresso': juridle.progresso(db, usuario.uuid), 'rodada': juridle.serializar(rodada)}


@router.post('/rodadas')
def iniciar(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    rodada = juridle.iniciar(db, usuario.uuid)
    return {'rodada': juridle.serializar(rodada), 'progresso': juridle.progresso(db, usuario.uuid)}


@router.post('/rodadas/{rodada_id}/respostas')
def responder(rodada_id: str, dados: Resposta, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    rodada, resultado = juridle.responder(db, usuario.uuid, rodada_id, dados.pergunta, dados.opcao)
    return {'rodada': juridle.serializar(rodada), 'resultado': resultado,
            'progresso': juridle.progresso(db, usuario.uuid)}
